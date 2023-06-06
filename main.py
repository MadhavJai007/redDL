import json
import os
import io
import sys
import re
import yt_dlp
import yaml
import gallery_dl
import urllib.parse
import urllib.error
import argparse
from gallery_dl import config, job
from sys import argv
from dotenv import dotenv_values
from models.logger import YTDLPLogger
from models.yaml_config import RedDLConfig

# TODO: Refactor

# TODO: Useless code
def generate_user_agent():
    # random user agent string
    # needed for accessing reddit post info
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'

# TODO: Useless code
# referenced from https://stackoverflow.com/questions/23793987/write-file-to-a-directory-that-doesnt-exist
def safe_open_wb(path, to_create):
    # open a path, creating it if needed
    if to_create:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, 'wb')


def my_hook(d):
    progress_milestones = ["0.0%", "25.0%", "50.0%", "99.0%"]

    if d['status'] == "downloading":
        print(f'> ETA: {d["_eta_str"]} || Speed: {d["_speed_str"]} || Downloaded: {d["_downloaded_bytes_str"]} || Progress: {d["_percent_str"]}')
        # if d.get('eta') is not None:
            # if d["_percent_str"] in progress_milestones:
            #     print(f'> ETA: {d["_eta_str"]} || Speed: {d["_speed_str"]} || Downloaded: {d["_downloaded_bytes_str"]} || Progress: {d["_percent_str"]}')
    elif d['status'] == 'finished':
        print('Finished downloading, now post-processing...')
        print(f"File name: {d.get('filename')}")
    elif d['status'] == 'error':
        print('Uh oh. Stinky!')

def show_help():
    print(f'> Please use a command with atleast one argument! Like this: {os.path.basename(argv[0])} <URL_TO_POST_WITH_MEDIA>')

# Used to remove any query portion of the url before doing anything since it can cause problems later on.
def remove_query_string(url):
    queryIndex=url.find('?')
    if(queryIndex>=0):
        return url[:(url.find('?'))]
    return url

# method to load user defined variables from config file
def get_config_args():

    config_file_path = os.path.abspath('config.yaml')
    try:
        # load yaml file
        with open(config_file_path, 'r') as file:
            user_config = yaml.safe_load(file)

            main_arguments = user_config.get('mainArguments')
            file_output_strings = user_config.get('fileOutputStrings')

            yaml_config = RedDLConfig(main_arguments=main_arguments,
                                      file_output_names=file_output_strings)
            return yaml_config
    except FileNotFoundError as fnf_err:
        print(fnf_err)
        print("Config.yaml file is not present!!")
        print("Quitting...")
        quit()
    except yaml.YAMLError as yaml_err:
        print(f"Error reading YAML file: {yaml_err}")
        print("Quitting...")
        quit()
    except Exception as e:
        print(e)
        # printing type of exception
        # https://stackoverflow.com/a/9824060
        print(e.__class__.__name__)
        print("Quitting...")
        quit()

    # print(user_config)

# method to get arguments, and return them as an object
def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("url", type=str, help="url of the media you want to download")
    arg_parser.add_argument("-p", "--path", help="Base download directory", default=None, required=False)
    arg_parser.add_argument("--ds", "--domain_subfolder", action="store_true", default=False,
                            help="Including this flag means the download will be stored in a subfolder titled with the website's name")
    arg_parser.add_argument("--sub", "--subreddit", action="store_true", default=False,
                            help="Using this flag will put the download in the subreddit folder (reddit only)")
    arg_parser.add_argument("--mm", "--multiple-media", action="store_true", default=False,
                            help="Using this flag on a post with multiple media will download it in a subfolder named with the download name")
    arg_parser.add_argument("--igh", "--ig-highlight-folder", action="store_true", default=False,
                            help="Using this on an instagram highlight will download it in a 'higlights' subfolder")
    arg_parser.add_argument("--igs", "--ig-story-folder", action="store_true", default=False,
                            help="Using this on an instagram story will download it in a 'stories' subfolder")
    arg_parser.add_argument("-f", "--filename", help="Use this flag if you want a custom file name", default=None, required=False)
    args = arg_parser.parse_args()
    # print(f'args = {args}')
    # print(f'args.path={args.path}')
    # print(f'Domain subfolder flag={args.ds}')
    # print(f'media url={args.url}')

    # args_json = json.loads(json.dumps(vars(args)))
    # print(args_json["path"])
    return args


def confirm_args(config_args, cli_args):

    args_mapping = {
        'path': '_root_dl_folder',
        'ds': '_website_folder',
        'sub': '_subreddit_folder',
        'mm': '_multiple_media_folder',
        'igh': '_ig_highlights_folder',
        'igs': '_ig_stories_folder'
    }

    confirmed_args = {}

    # check if config's parameters should be used or not if cli args are present
    for key1, key2 in args_mapping.items():
        if vars(cli_args)[key1]== None or vars(cli_args)[key1] == False:
            confirmed_args[key2] = config_args.__dict__[key2]
        else:
            confirmed_args[key2] = vars(cli_args)[key1]

    confirmed_args["custom_filename"] = vars(cli_args)["filename"]

    for key, value in config_args.__dict__.items():
        if "_filename" in key:
            confirmed_args[key] = value

    return confirmed_args


def get_env_variables(key):
    try:
        return dotenv_values(".env")[key]
    except KeyError:
        raise Exception("Credentials missing in '.env' configuration! Ensure the .env file is configured correctly!")

def config_reddit_download(path, include_domain_subfolder, include_subreddit_subfolder,
                           include_multiple_media_subfolder, dl_name):

    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = {
        "submission_subdirectories": [],
        "submission_gallery_subdirectories": [],
        "imgur_gallery_subdirectories": [],
        "imgur_embed_subdirectories": [],
        "gfycat_embed_subdirectories": []
    }

    def modify_imgur_gfycat_str(file_str):
        modified_file_str = file_str
        modified_file_str = modified_file_str.replace("{category}", "reddit")
        modified_file_str = modified_file_str.replace("{subreddit}", "{_reddit[subreddit]}")
        modified_file_str = modified_file_str.replace("{title[:120]}", "{_reddit[title][:120]}")
        modified_file_str = modified_file_str.replace("{id}", "{_reddit[id]}")
        return modified_file_str

    gallery_post_subfolder_name = dl_name
    gallery_post_subfolder_name = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", gallery_post_subfolder_name)

    imgur_gallery_subfolder_name = modify_imgur_gfycat_str(dl_name)
    imgur_gallery_subfolder_name = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", imgur_gallery_subfolder_name)

    reddit_submission_filename = "%s.{extension}" % dl_name
    imgur_gfycat_embed_filename = "%s.{extension}" % modify_imgur_gfycat_str(dl_name)
    # imgur_gfycat_embed_filename = imgur_gfycat_embed_filename.replace("{category}", "reddit")
    # imgur_gfycat_embed_filename = imgur_gfycat_embed_filename.replace("{subreddit}", "{_reddit[subreddit]}")
    # imgur_gfycat_embed_filename = imgur_gfycat_embed_filename.replace("{title[:120]}", "{_reddit[title][:120]}")
    # imgur_gfycat_embed_filename = imgur_gfycat_embed_filename.replace("{id}", "{_reddit[id]}")

    if include_domain_subfolder:
        for x in subdirectories:
            # skipping these two otherwise gallery-dl makes a duplicate subfolder
            if x.startswith("imgur") or x.startswith("gfycat"):
                continue
            subdirectories[x].append("reddit")

    if include_subreddit_subfolder:
        for x in subdirectories:
            if x.startswith("imgur") or x.startswith("gfycat"):
                continue
            else:
                subdirectories[x].append("{subreddit}")


    # for posts that have multiple images, make another subfolder
    if include_multiple_media_subfolder:
        subdirectories["submission_gallery_subdirectories"].append(gallery_post_subfolder_name)
        subdirectories["imgur_gallery_subdirectories"].append(imgur_gallery_subfolder_name)

    """ setting reddit config """
    config.set(("extractor",), "reddit", {
        "#": "only spawn child extractors for links to specific sites",
        "whitelist": ["imgur", "gfycat"],
        "#": "put files from child extractors into the reddit directory",
        "parent-directory": True,
        "#": "transfer metadata to any child extractor as '_reddit'",
        "parent-metadata": "_reddit",
        "submission": {
            "directory": {
                "locals().get('is_gallery')": subdirectories["submission_gallery_subdirectories"],
                "": subdirectories["submission_subdirectories"]
            },
            "filename": {
                "locals().get('is_gallery')": reddit_submission_filename,
                "": reddit_submission_filename
            }
        },
        "videos": True
    })

    """ imgur embed config """
    config.set(("extractor", "imgur", "album", "directory",), "'_reddit' in locals()", subdirectories["imgur_gallery_subdirectories"])
    config.set(("extractor", "imgur", "album", "filename",), "'_reddit' in locals()", imgur_gfycat_embed_filename)
    config.set(("extractor", "imgur", "directory",), "'_reddit' in locals()", subdirectories["imgur_embed_subdirectories"])
    config.set(("extractor", "imgur", "filename",), "'_reddit' in locals()", imgur_gfycat_embed_filename)
    config.set(("extractor", "imgur",), "mp4", True)
    config.set(("extractor", "imgur",), "keyword", "")

    """ gfycat embed config """
    config.set(("extractor", "gfycat", "directory",), "'_reddit' in locals()", subdirectories["gfycat_embed_subdirectories"])
    config.set(("extractor", "gfycat", "filename",), "'_reddit' in locals()", imgur_gfycat_embed_filename)

def config_twitter_download(path, include_domain_subfolder, include_multiple_media_subfolder, dl_name):

    # loading twitter account credentials from env file
    try:
        twt_usrname = get_env_variables('TWITTER_USERNAME')
        twt_password = get_env_variables('TWITTER_PASSWORD')
    except Exception as e:
        print(e)
        quit()

    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("twitter")

    multiple_media_subfolder_name = dl_name
    multiple_media_subfolder_name = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", multiple_media_subfolder_name)

    mm_subdirectories = []
    if include_multiple_media_subfolder:
        mm_subdirectories.append(multiple_media_subfolder_name)

    file_str = "%s.{extension}" % dl_name
    # "{category}_@{user[name]} - {num:?//>02} {empty|content[:160]} [{tweet_id}].{extension}"

    # configure twitter download path and filename
    config.set(("extractor",), "twitter", {
        "username": twt_usrname,
        "password": twt_password,
        "directory": {
                "count > 1": subdirectories + mm_subdirectories,
                "": subdirectories
        },
        "filename": file_str
    })

def config_instagram_download(path, include_domain_subfolder, include_multiple_media_subfolder,
                              dl_name, dl_story_name, dl_hlighlight_name,
                              include_ig_highlight_subfolder, include_ig_story_subfolder):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    subdirectories_story = []
    subdirectories_highlight = []

    if include_domain_subfolder:
        subdirectories.append("instagram")
        subdirectories_story.append("instagram")
        subdirectories_highlight.append("instagram")

    if include_ig_story_subfolder:
        subdirectories_story.append("stories")

    if include_ig_highlight_subfolder:
        subdirectories_highlight.append("highlights")


    mm_subfolder_name = dl_name
    mm_subfolder_name = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", mm_subfolder_name)

    mm_subfolder_name_story = dl_story_name
    mm_subfolder_name_story = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", mm_subfolder_name_story)
    mm_subfolder_name_story = re.sub(r"\({date}\)", "", mm_subfolder_name_story)

    mm_subfolder_name_highlight = dl_hlighlight_name
    mm_subfolder_name_highlight = re.sub(r" \{num:\?\/\/>[A-Za-z0-9]{2}\}", "", mm_subfolder_name_highlight)

    mm_subdirectories = []
    mm_subdirectories_story = []
    mm_subdirectories_highlight = []

    if include_multiple_media_subfolder:
        mm_subdirectories.append(mm_subfolder_name)
        mm_subdirectories_story.append(mm_subfolder_name_story)
        mm_subdirectories_highlight.append(mm_subfolder_name_highlight)

    highlight_file_name = "%s.{extension}" % dl_hlighlight_name
    story_file_name = "%s" % dl_story_name
    post_file_name = "%s.{extension}" % dl_name

    config.set(("extractor",), "instagram", {
        "keyword": "",
        "cookies": "./cookies-instagram.txts",
        "stories": {
            "directory": {
                "count > 1": subdirectories_story + mm_subdirectories_story,
                "": subdirectories_story
            },
            "filename": story_file_name
        },
        "highlights": {
            "directory": {
                "count > 1": subdirectories_highlight + mm_subdirectories_highlight,
                "": subdirectories_highlight
            },
            "filename": highlight_file_name
        },
        "posts": {
            "directory": {
                "count > 1": subdirectories + mm_subdirectories,
                "": subdirectories
            },
            "filename": post_file_name
        },
        "reels": {
            "directory": {
                "count > 1": subdirectories + mm_subdirectories,
                "": subdirectories
            },
            "filename": post_file_name
        },
        "directory": {
            "count > 1": subdirectories + mm_subdirectories,
            "": subdirectories
        },
        "filename": post_file_name,
        "videos": True
    })

def config_imgur_download(path, include_domain_subfolder, include_multiple_media_subfolder, dl_name):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    # image_count = extract_keyword_attr(url, "count")

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("imgur")

    mm_subdirectories = []
    if include_multiple_media_subfolder:
        mm_subdirectories.append("{category} - [{album[id]}]")
        # "{category} - {empty|album[title][:120]}... [{album[id]}]"

    imgur_filename = "%s.{extension}" % dl_name if dl_name is not None else "{category} - {num:?//>02}. {title[:120]}... [{id}].{extension}"

    """ configuring imgur download properties"""
    config.set(("extractor",), "imgur", {
        "keyword": "",
        "#": "use different directory and filename formats when coming from a reddit post",
        "album": {
            "directory": {
                "album['image_count'] > 1": subdirectories + mm_subdirectories,
                "": subdirectories
            },
            # subdirectories + ["{category} - {empty|album[title][:120]}... [{album[id]}]"], # if int(image_count) > 1 else [],
            "filename": imgur_filename
        },
        "directory": subdirectories,
        "filename": imgur_filename,
        "mp4": True
    })


def extract_keyword_attr(url, attr):
    # Redirect the standard output to a buffer
    stdout_buffer = io.StringIO()
    sys.stdout = stdout_buffer
    datajob = job.KeywordJob(url)
    datajob.run()
    # Restore the standard output
    sys.stdout = sys.__stdout__
    # Get the printed output from the buffer
    printed_output = stdout_buffer.getvalue()

    # Split the captured output into lines
    lines = printed_output.strip().split('\n')
    # Initialize the JSON object
    keywords_obj = {}
    # Iterate over the lines and extract key-value pairs
    current_section = None
    for i, line in enumerate(lines):
        if line.endswith(':'):
            # Found a new section
            current_section = line[:-1].strip()
            keywords_obj[current_section] = {}
        elif "-----" in line:
            continue
        elif line.startswith(" "):
            continue
        else:
            if current_section:
                # make a key-value pair
                keywords_obj[current_section][line.strip()] = lines[i + 1].strip()
    # Convert the JSON object to a JSON string
    json_string = json.dumps(keywords_obj, indent=4)
    # Print the JSON string
    print(json_string)
    return keywords_obj[attr]


def config_gfycat_download(path, include_domain_subfolder, dl_name):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("gfycat")

    gfycat_filename = "%s.{extension}" % dl_name if dl_name is not None else "{category}_@{username} - {title[:160]} [{gfyId}].{extension}"
    # gfycat_filename = "{category}_@{username} - {title[:160]} [{gfyId}].{extension}"

    """ configuring gfycat download properties """
    config.set(("extractor",), "gfycat", {
        "#": "use different directory and filename formats when coming from a reddit post",
        "directory": subdirectories,
        "filename": gfycat_filename
    })


# using yt-dl specifically for tiktok videos
def download_tiktok(url, path, include_subfolder, dl_name):
    # call yt-dlp downloader

    output_directory = os.path.abspath(path)
    if(include_subfolder):
        subfolder = os.path.dirname("./tiktok/")
        output_directory = os.path.abspath(os.path.join(path, subfolder))
    ydl_opts = {
        'logger': YTDLPLogger(),
        # 'progress_hooks': [my_hook],
        'outtmpl': f'{output_directory}/{dl_name}.%(ext)s'
    }
    ydl = yt_dlp.YoutubeDL(ydl_opts)
    try:
        # help(yt_dlp.YoutubeDL)
        ydl.download(url)
        # info = ydl.extract_info(url, download=False)
        # print(json.dumps(ydl.sanitize_info(info)))
        print('> Downloaded succesfully!')
        # break
    except yt_dlp.DownloadError as e:
        print(e)

# fallback download method for other urls
def download_yt_dlp_generic(url, path, include_subfolder):
    # TODO: Implement multiple retries and progress bar
    gallery_dl_no_extractor_error = 0
    yt_dlp_no_extractor_error = 0

    try:
        # setting path from argument
        config.set(("extractor",), "base-directory", os.path.abspath(path))
        """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
        if not include_subfolder:
            found_extractor = f'{job.extractor.find(url)}'
            extractor_name = found_extractor.split('.')[2]
            config.set(("extractor",), extractor_name, {
                "#": "customizing path subdirectories",
                "directory": {
                    "": []
                }
            })

        # run the download job
        resss = job.DownloadJob(url)
        resss.run()

    except gallery_dl.exception.NoExtractorError as e:
        gallery_dl_no_extractor_error = 1
        print("> No gallery_dl extractor for this url found. Video url maybe?")
        print(e)
    except Exception as e:
        gallery_dl_no_extractor_error = 1
        print("> Unexpected error. Retrying with yt-dlp")
        print(e)

    # if media couldnt be downloaded with gallery dl try using yt-dlp
    if (gallery_dl_no_extractor_error):
        print("> Checking with yt-dlp...")
        try:
            output_directory = os.path.abspath(path)
            if (include_subfolder):
                subfolder = os.path.dirname(f'./%(extractor)s/')
                output_directory = os.path.abspath(os.path.join(path, subfolder))
            ydl_opts = {
                'logger': YTDLPLogger(),

                # 'progress_template': 'download',
                'quiet': False,
                # 'progress_hooks': [my_hook],
                'outtmpl': f'{output_directory}/%(extractor)s - %(title).120s.. [%(id)s].%(ext)s'
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            # help(yt_dlp.YoutubeDL)
            ydl.download(url)
            # info = ydl.extract_info(url, download=False)
            # print(json.dumps(ydl.sanitize_info(info)))
            print('> Downloaded successfully!')
            # break
        except yt_dlp.DownloadError as e:
            yt_dlp_no_extractor_error = 1
            print("> Could not download the video. Video could be unavailable")
            print(e)
        except Exception as e:
            yt_dlp_no_extractor_error = 1
            print("> Unexpected error occured...")
            print(e)

    if (yt_dlp_no_extractor_error):
        print("> The media could not be downloaded. The URL could be incorrectly formatted or its not supported")
    else:
        print("> Media downloaded")




# Checking if the given url is one of the supported websites by redDL
def match_domain(url, domain_list):
    parsed_url = urllib.parse.urlparse(url)
    domain_name = parsed_url.netloc.lower()

    for domain in domain_list:
        if domain[1:] in domain_name and domain_name.endswith(domain[1:]):
            domain_without_star = domain[1:]
            main_domain = domain_without_star.split('.')[0]
            return main_domain
    if 'tiktok' in domain:
        return 'tiktok'
    else:
        return None


def gallery_dl_download(url):
    try:
        gallery_dl_dowbload_job = job.DownloadJob(url)
        gallery_dl_dowbload_job.run()
    except Exception as error:
        print("Something went wrong!")
        print(error)
def gallery_dl_get_info(url):
    keyword_data = job.KeywordJob(url)
    keyword_data.run()

    # extracted_info = gallery_dl.extractor.find(url)
    # for att in dir(extracted_info):
    #     print(att, getattr(extracted_info,att))
    # for x in extracted_info:
    #     print(x)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('PyCharm')

    # loading any user defined arguments in yaml config file.
    config_file_args = get_config_args()

    # loading command line parameters (will override) config file parameters
    cli_args = get_args()

    # override config file arguments if parameters passed through command line
    args_dict = confirm_args(config_file_args, cli_args)

    # print(json.dumps(args_dict, indent=4))

    arg_download_path = args_dict["_root_dl_folder"]
    include_domain_subfolder = args_dict["_website_folder"]
    include_subreddit_subfolder = args_dict["_subreddit_folder"]
    include_multiple_media_subfolder = args_dict["_multiple_media_folder"]
    include_ig_highlight_subfolder = args_dict["_ig_highlights_folder"]
    include_ig_story_subfolder = args_dict["_ig_stories_folder"]
    custom_file_name = args_dict["custom_filename"]



    parsed_url = urllib.parse.urlparse(cli_args.url)
    domain = parsed_url.netloc

    domains = ['*reddit.com', '*twitter.com', '*instagram.com', '*imgur.com', '*gfycat.com']
    print("Supported domains : " + str(domains))

    matched_domain = match_domain(cli_args.url, domains)
    print(f"Supported domain found: {matched_domain}") if matched_domain else print("Unfamiliar domain found...")
    if matched_domain:
        match matched_domain:
            case "reddit":
                dl_name = custom_file_name if custom_file_name is not None else args_dict["_reddit_filename"]
                config_reddit_download(arg_download_path, include_domain_subfolder,
                                       include_subreddit_subfolder, include_multiple_media_subfolder,
                                       dl_name)
                gallery_dl_download(cli_args.url)
                # gallery_dl_get_info(cli_args.url)
            case "twitter":
                dl_name = custom_file_name if custom_file_name is not None else args_dict["_twitter_filename"]
                config_twitter_download(arg_download_path, include_domain_subfolder,
                                        include_multiple_media_subfolder, dl_name)
                gallery_dl_download(cli_args.url)
                # gallery_dl_get_info(cli_args.url)
            case "instagram":
                dl_name = custom_file_name if custom_file_name is not None else args_dict["_ig_post_filename"]
                dl_story_name = custom_file_name if custom_file_name is not None else args_dict["_ig_story_filename"]
                dl_highlight_name = custom_file_name if custom_file_name is not None else args_dict["_ig_highlight_filename"]
                config_instagram_download(arg_download_path, include_domain_subfolder, include_multiple_media_subfolder, dl_name, dl_story_name, dl_highlight_name, include_ig_highlight_subfolder, include_ig_story_subfolder)
                gallery_dl_download(cli_args.url)
                # gallery_dl_get_info(cli_args.url)
            case "imgur":
                dl_name = custom_file_name
                config_imgur_download(arg_download_path, include_domain_subfolder, include_multiple_media_subfolder, dl_name)
                gallery_dl_download(cli_args.url)
            case "gfycat":
                dl_name = custom_file_name
                config_gfycat_download(arg_download_path, include_domain_subfolder, dl_name)
                gallery_dl_download(cli_args.url)
            case other:
                print("???")
    elif 'tiktok.com' in domain:
        dl_name = custom_file_name if custom_file_name is not None else args_dict["_tiktok_filename"]

        # using a method that uses yt-dlp to download tiktok videos
        print(f'> Using yt-dl for tiktok')
        download_tiktok(cli_args.url, arg_download_path, include_domain_subfolder, dl_name)
    else:
        # using a generic download method that attempts to use gallery-dls/yt-dlp's default configuration for that site.
        print(f'> Using fallback download method')
        download_yt_dlp_generic(cli_args.url, arg_download_path, include_domain_subfolder)
