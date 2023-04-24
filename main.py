import json
import os
import shutil
import subprocess
import errno
import re
import yt_dlp
import fnmatch
from bs4 import BeautifulSoup
from gallery_dl import config, job
import gallery_dl
import urllib.parse
from requests import get, exceptions
import argparse
from sys import argv
from dotenv import load_dotenv
from logger import YTDLPLogger

# TODO: config settings
# Attempt to read any configuration settings
try:
    # importing root down
    from user_config import ROOT_DOWNLOADS_FOLDER as user_root_path
    print("> Custom root download path in user config.")
    print("> Validating path...")

    if isinstance(user_root_path, str) and len(user_root_path.strip()) > 0:
        # check if path can be used as a directory
        if os.path.isdir(user_root_path):
            print(f'> Directory exists...')
            root_download_path = os.path.abspath(user_root_path)
            print(f'> User configured download directory: {root_download_path}\n')
        else:
            # create the directoruser_root_path if they dont exist
            print(f'> Directory does not exist. Creating..')
            os.makedirs(user_root_path)
            root_download_path = os.path.abspath(user_root_path)
            print(f'> Created user configured download directory: {root_download_path}\n')
    else:
        # raise exception if invalid path string in config file
        raise Exception("Invalid Path. Falling back to default download path in user profile.")
except ImportError:
    print("> Import config attempt failed!")
    print("> Setting default values...")

    # setting a default downloads directory in user profile director
    user_profile_path = os.environ.get('USERPROFILE')
    default_download_folder = os.path.dirname("./redDL downloads/")
    root_download_path = os.path.abspath(os.path.join(user_profile_path, default_download_folder))
    print(f'> Finalized default root downloads folder: {root_download_path}\n')

# user configurable download path (user_config.py)
# print(f'> Confirmed Root download folder: {Home_download_path}')


def set_up_gallery_dl(base_dir):

    # loading any available env files
    load_dotenv()
    # gallery-dl configuration
    config.load()  # load default config files
    # Todo: put all the extractor properties in a different file
    config.set(("extractor",), "base-directory", base_dir)
    config.set(("extractor",), "reddit", {
        "#": "only spawn child extractors for links to specific sites",
        "whitelist": ["imgur", "redgifs", "gfycat"],

        "#": "put files from child extractors into the reddit directory",
        "parent-directory": True,

        "#": "transfer metadata to any child extractor as '_reddit'",
        "parent-metadata": "_reddit",
        "submission": {
            "directory": {
                "locals().get('is_gallery')": ["{category}_{subreddit} - {title[:160]} [{id}]"],
                "": []
            },
            "filename": {
                "locals().get('is_gallery')": "{category}_{subreddit} - {num:?//>02}. {title[:160]} [{id}].{extension}",
                "": "{category}_{subreddit} - {num:?//>02} {title[:160]} [{id}].{extension}"
            }
        },
        "videos": True
    })
    config.set(("extractor",), "imgur", {
        "keyword": "",
        "#": "use different directory and filename formats when coming from a reddit post",
        "album": {
            "directory":
                {
                    "'_reddit' in locals()": ["reddit_{_reddit[subreddit]} - {_reddit[title][:160]} [{_reddit[id]}]"],
                    # "'album' in locals()": ["albums"],
                    "": ["{category} - {empty|album[title][:160]} [{album[id]}]"]
                },
            "filename":
                {
                    "'_reddit' in locals()": "reddit_{_reddit[subreddit]} - {num:?//>02}. {_reddit[title][:160]} [{_reddit[id]}].{extension}",
                    "": "{category} - {num:?//>02}. {title[:160]} [{id}].{extension}"
                },
        },
        "directory":
            {
                "'_reddit' in locals()": [],
                # "'album' in locals()": ["albums"],
                "": []
            },
        "filename":
            {
                "'_reddit' in locals()": "reddit_{_reddit[subreddit]} - {num:?//>02}. {_reddit[title][:160]} [{_reddit[id]}].{extension}",
                "": "{category} - {num:?//>02}. {title[:160]} [{id}].{extension}"
            },
        "mp4": True
    })
    config.set(("extractor",), "gfycat", {
        "#": "use different directory and filename formats when coming from a reddit post",
        "directory": {
            "'_reddit' in locals()": [],
            "": []
         },
        "filename":{
            "'_reddit' in locals()": "reddit_{_reddit[subreddit]} - {num:?//>02}. {_reddit[title][:160]} [{_reddit[id]}].{extension}",
            "": "{category}_@{username} - {title[:160]} [{gfyId}].{extension}"
        }
    })
    config.set(("extractor",), "twitter", {
        "#": "use different directory and filename formats when coming from a reddit post",
        "username": os.getenv('TWITTER_USERNAME'),
        "password": os.getenv('TWITTER_PASSWORD'),
        "directory":  [],
        "filename": "{category}_@{user[name]} - {num:?//>02} {empty|content[:160]} [{tweet_id}].{extension}"
    })
    config.set(("extractor",), "instagram", {
        "keyword": "",
        "cookies": "./cookies-instagram.txt",
        "stories": {
            "directory": [],
            "filename": "{category}_@{username} - {num:?//>02}. Story-({date}) [{post_shortcode}].{extension}"
        },
        "highlights": {
            "directory": ["highlights"],
            "filename": "{category}_@{username} - {num:?//>02}. {highlight_title} [{post_shortcode}].{extension}"
        },
        "posts": {
            "directory": [],
            "filename": "{category}_@{username} - {num:?//>02}. {description[:160]} ({location_slug}) [{post_shortcode}].{extension}"
        },
        "reels": {
            "directory": [],
            "filename": "{category}_@{username} - {num:?//>02}. {description[:160]} ({location_slug}) [{post_shortcode}].{extension}"
        },
        "directory": [],
        "filename": "{category}_@{username} - {num:?//>02}. {description[:160]} ({location_slug}) [{post_shortcode}].{extension}",
        "videos": True
    })
    # config.set(("downloader",), "ytdl", {
            # "format": null,
            # "forward-cookies": false,
            # "logging": true,
            # "module": null,
            # "outtmpl": null,
            # "raw-options": null,
			# "#": "use yt-dlp instead of youtube-dl",
            # "module": "yt_dlp"
    # })

image_extensions = ["jpg", "png", "jpeg", "gif"]

""" 
IMPORTANT:
https://www.reddit.com/r/gaming/comments/11qi515/the_year_is_2007_summer_break_just_started_i_just/
is equivalent to
https://www.reddit.com/r/gaming/comments/11qi515
is equivalent to
https://www.reddit.com/comments/11qi515

Basically the subreddit and post title portion of the url is unnecessary
"""

# TODO: SPLIT INTO MORE FUNCTIONS AND MODULES

def generate_user_agent():
    # random user agent string
    # needed for accessing reddit post info
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'


def say(text, type=''):
    if type == 'error':
        prefix = '\nERROR: '
    else:
        prefix = '[>] '

    print(prefix + text)


def get_post(url):

    #TODO = GIve warning if url is not from reddit domain
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.netloc != 'www.reddit.com' : #TODO: Include any reddit subdomains through regex
        print(f'> WARNING: NON REDDIT URL DETECTED')

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    try:  # checks if link is valid
        r = get(
            url + '.json',
            headers=headers
        )
    except exceptions.MissingSchema:
        print('Please provide a valid URL')
        quit()
    except exceptions.InvalidSchema:
        print('Please provide a valid URL')
        quit()
    except exceptions.InvalidJSONError:
        print('Please provide a reddit URL')
        quit()
    except exceptions.ConnectionError:
        print('A connection error occured')
        quit()
    except exceptions.Timeout:
        print("The request attempt timedout. Reddit may be down.")
        quit()


    # if reddit post is unavailable
    if 'error' in r.text:
        if r.status_code == 404:
            print('Post unavailable or deleted')
            quit()

    try:
        json_data = json.loads(r.text)[0]['data']['children'][0]['data']
        print('Post Found!')
        print(f'> Title: {json_data["title"]}')
        print(f'> Sub-reddit: {json_data["subreddit_name_prefixed"]}')
        print(f'> Posted by: {json_data["author"]}')
        # print(f'> { ((json_data["post_hint"]), "Text")  ["post_hint" in json_data ] }')
        # print(f'> Is reddit media domain: {json_data["is_reddit_media_domain"]}')
    except json.decoder.JSONDecodeError:
        print('ERROR: Post not found')
        quit()

    """ determines the post type"""
    """
        possible values for "post_hint" attribute: 

        link  (only examples i've seen:  Imgur)
        image (for both regular imgs and gifs)
        hosted:video (reddit video)
        rich:video (external media embeds like youtube)
    """
    """ is_gallery attribute for gallery posts"""
    post_type = json_data["post_hint"] if "post_hint" in json_data else "gallery" if "is_gallery" in json_data else "text"
    print(f'> Post type: {post_type}')
    print(json_data["url"])

    # extracting the media's domain information from the response.
    try:
        domain = json_data["domain"]
        print(f'> Domain: {domain}')
    except KeyError:
        # if there is no domain attribute, use the domain portion of the url attribute
        parsed_url = urllib.parse.urlparse(json_data['url'])
        domain = parsed_url["netloc"]
        domain2 = ".".join(json_data["url"].split("/")[2].split(".")[-2:])
        print(f'> Domain: {domain}')
        print(f'> Domain: {domain2}')

    # TODO: Extract permalink attribute for output name configuration
    permalink = json_data["permalink"]
    # split so different parts of the url can be used later
    permalink_attr = permalink.split("/")
    post_id = permalink_attr[4]
    readable_name = permalink_attr[5]
    readable_name = readable_name.replace("_", " ")
    print(f'> Post ID: {post_id}')
    print(f'> Readable name: {readable_name}')

    # getting extension portion of from the url attribute
    extension = json_data["url"].split(".")[-1]

    """ doing different things based on the determined domain """

    # TODO: Check if it is an imgur gallery
    # TODO: implement gallery-dl integration
    # if it is determined to be an imgur gallery or album, redDL will ignore it
    if "imgur.com" in domain and ("gallery" in json_data["url"] or "/a/" in json_data["url"]):
        print("WARNING: This is an Imgur album. Not currently supported by redDL. Exiting...")


    # if determined to be a reddit gallery post
    # NOTE: Have to use the "url_overridden_by_dest" attribute to get the gallery link
    # since the "url" attribute redirects to an outbound url that is associated with the gallery images
    elif "reddit.com" in domain and "gallery" in json_data["url_overridden_by_dest"]:
            print("> This is a gallery post")
            img_urls = get_gallery_data(json_data["gallery_data"], json_data["media_metadata"], readable_name, json_data["subreddit"], post_id)
            print(img_urls)

    # if determined to be an image, download it
    elif extension in image_extensions:
        print(f'> Downloading image from: {json_data["url"]}')
        result = download_img(json_data["url"], readable_name, json_data["subreddit"], False, post_id)
        print(result)

    else:
        # TODO: Change video title according to user config.
        # TODO: account for subreddit directory
        print("Regular media post. Downloading...")
        # call yt-dlp downloader
        ydl_opts = {
            'logger': YTDLPLogger(),
            'progress_hooks': [my_hook],
            'outtmpl': f'{json_data["subreddit"]} - {readable_name} [{post_id}].%(ext)s'
        }

        ydl = yt_dlp.YoutubeDL(ydl_opts)

        # TODO: user configurable download retries
        max_download_attempts = 2
        for i in range(max_download_attempts):
            try:
                # help(yt_dlp.YoutubeDL)
                ydl.download(url)
                # info = ydl.extract_info(url, download=False)
                # print(json.dumps(ydl.sanitize_info(info)))
                print('> Downloaded succesfully!')
                break
            except yt_dlp.DownloadError as e:
                print(f'> Download attempt {i+1} failed!')

                if "Unsupported URL" in str(e):
                    print("> The URL is not supported by YT-DLP. Operation aborted")
                    break

                if "No media found" in str(e):
                    print("> The reddit post has no media! Ensure it's not a text post. Operation aborted")
                    break

                if (i+1) < max_download_attempts:
                    print(f'> Attempting {max_download_attempts - (i+1)} more time')
                    print('...\n')
        else:
            print('All attempts to download video failed!')

    #     """ REFERENCED FROM: https://stackoverflow.com/questions/9823936/how-do-i-determine-what-type-of-exception-occurred """
    #     # except Exception as ex:
    #     #     template = "An exception of type {0} occurred. Arguments:\n{1!r}"
    #     #     message = template.format(type(ex).__name__, ex.args)
    #     #     print(message)


# function to download image
def download_img(img_url, img_name, subreddit, enable_gallery_subfolder, post_id, post_title=""):
    response = get(img_url, stream = True)
    # TODO: overwrite checks
    # getting the image type extension
    img_type = img_url.split(".")[-1]
    # preparing the image's name
    img_name = f'{subreddit} - {img_name} [{post_id}].{img_type}'
    # setting path where image will be stored
    full_path = img_name
    # flag for creating a gallery post subfolder.
    to_create = False
    if enable_gallery_subfolder:
        # modifying path to include new subfolder for gallery images.
        print("> GALLERY SUBFOLDER ENABLED")
        full_path = f'./{subreddit} - {post_title} [{post_id}]/{img_name}'
        to_create = True

    # downloading image to disk
    if response.status_code == 200:
        print(f'> Image path: {full_path}')
        with safe_open_wb(full_path, to_create) as f:
            shutil.copyfileobj(response.raw, f)
        print('> Image successfully Downloaded: ', img_name)
        return "Success"
    else:
        print("> ERROR: Couldn't retrieve the image!!")
        return "Fail"

# function to get the different image ids in the gallery and create downloadable links out of them
def get_gallery_data(gallery_data_obj, media_metadata_list, fallback_title, subreddit, post_id):
    gallery_img_list = gallery_data_obj["items"]
    reddit_img_netloc = "https://i.redd.it/"
    results_list = []
    for idx, img_id in enumerate(gallery_img_list):
        media_id = img_id["media_id"]
        # if the image has a caption
        caption = img_id["caption"] if "caption" in img_id else "None"
        # if any associated link is with the image
        outbound_url = img_id["outbound_url"] if "outbound_url" in img_id else "None"
        # getting the image type extension
        img_type = media_metadata_list[media_id]["m"]
        img_type = img_type[img_type.find("image/")+6:]

        print(f'> {idx+1}. Caption: {caption}')
        print(f'> {idx+1}. Outbound link: {outbound_url}') # TODO: unused
        print(f'> {idx+1}. {reddit_img_netloc}{media_id}.{img_type}')

        # creating the direct img url to download from
        img_url = f'{reddit_img_netloc}{media_id}.{img_type}'
        # the name of the image. will use associated caption if one is found, otherwise will just use the post's title.
        # if the post tile is used, pics can be differentiated using the number on the front
        img_file_name = f'{idx+1}. {caption if caption != "None" else fallback_title}'
        result = download_img(img_url, img_file_name, subreddit, True, post_id, fallback_title)
        results_list.append(result)

    return results_list


# referenced from https://stackoverflow.com/questions/23793987/write-file-to-a-directory-that-doesnt-exist
def safe_open_wb(path, to_create):
    # open a path, creating it if needed
    # TODO: account for sub reddit specific directories
    if to_create:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, 'wb')


def my_hook(d):
    if d['status'] == "downloading":
        if d.get('eta') is not None:
            print(f'> ETA: {d["_eta_str"]} || Speed: {d["_speed_str"]} || Downloaded: {d["_downloaded_bytes_str"]} || Progress: {d["_percent_str"]}')
    elif d['status'] == 'finished':
        print('Finished downloading, now post-processing...')
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

# method to get arguments, and return them as an object
def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("url", type=str, help="url of the media you want to download")
    arg_parser.add_argument("-p", "--path", help="Base directory", default="./", required=False)
    arg_parser.add_argument("--ds", "--domain_subfolder", action="store_true", default=False,
                            help="Including this flag means the download will be stored in the website's subfolder")
    args = arg_parser.parse_args()
    # print(f'args = {args}')
    # print(f'args.path={args.path}')
    # print(f'Domain subfolder flag={args.ds}')
    # print(f'media url={args.url}')

    # args_json = json.loads(json.dumps(vars(args)))
    # print(args_json["path"])
    return args


def config_reddit_download(path, include_domain_subfolder):

    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = {
        "submission_subdirectories": [],
        "submission_gallery_subdirectories": [],
        "imgur_gallery_subdirectories": [],
        "imgur_embed_subdirectories": [],
        "gfycat_embed_subdirectories": []
    }
    gallery_post_subfolder_name = "{category}_{subreddit} - {title[:120]}.. [{id}]"
    imgur_gallery_subfolder_name = "reddit_{_reddit[subreddit]} - {_reddit[title][:120]}... [{_reddit[id]}]"
    reddit_submission_filename = "{category}_{subreddit} - {num:?//>02} {title[:120]}.. [{id}].{extension}"
    imgur_gfycat_embed_filename = "reddit_{_reddit[subreddit]} - {num:?//>02}. {_reddit[title][:120]}... [{_reddit[id]}].{extension}"

    if include_domain_subfolder:
        for x in subdirectories:
            if x.startswith("imgur") or x.startswith("gfycat"):
                continue
            subdirectories[x].append("reddit")

    # TODO: another if statment for subreddit domain folder

    # for posts that have multiple images, make another subfolder
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

def config_twitter_download(path, include_domain_subfolder):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("twitter")

    # configure twitter download path and filename
    config.set(("extractor",), "twitter", {
        "#": "use different directory and filename formats when coming from a reddit post",
        "username": os.getenv('TWITTER_USERNAME'),
        "password": os.getenv('TWITTER_PASSWORD'),
        "directory": subdirectories,
        "filename": "{category}_@{user[name]} - {num:?//>02} {empty|content[:160]} [{tweet_id}].{extension}"
    })

def config_instagram_download(path, include_domain_subfolder):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("instagram")

    highlight_file_name = "{category}_@{username} - {num:?//>02}. {highlight_title} ({date}) [{post_shortcode}].{extension}"
    story_file_name =  "{category}_@{username} - {num:?//>02}. Story-({date}) [{post_shortcode}].{extension}"
    post_file_name = "{category}_@{username} - {num:?//>02}. {description[:120]} ({location_slug}) [{post_shortcode}].{extension}"

    config.set(("extractor",), "instagram", {
        "keyword": "",
        "cookies": "./cookies-instagram.txt",
        "stories": {
            "directory": subdirectories+["stories"] if include_domain_subfolder else subdirectories,
            "filename": highlight_file_name
        },
        "highlights": {
            "directory": subdirectories+["highlights"] if include_domain_subfolder else subdirectories,
            "filename": story_file_name
        },
        "posts": {
            "directory": subdirectories,
            "filename": post_file_name
        },
        "reels": {
            "directory": subdirectories,
            "filename": post_file_name
        },
        "directory": subdirectories,
        "filename": post_file_name,
        "videos": True
    })

def config_imgur_download(path, include_domain_subfolder):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("imgur")
    imgur_filename = "{category} - {num:?//>02}. {title[:120]}... [{id}].{extension}"

    """ configuring imgur download properties"""
    config.set(("extractor",), "imgur", {
        "keyword": "",
        "#": "use different directory and filename formats when coming from a reddit post",
        "album": {
            "directory": subdirectories + ["{category} - {empty|album[title][:120]}... [{album[id]}]"],
            "filename": imgur_filename
        },
        "directory": subdirectories,
        "filename": imgur_filename,
        "mp4": True
    })

def config_gfycat_download(path, include_domain_subfolder):
    # setting path from argument
    config.set(("extractor",), "base-directory", os.path.abspath(path))

    """ If the the ds flag is not included then dont make a subfolder (otherwise default behavior)"""
    subdirectories = []
    if include_domain_subfolder:
        subdirectories.append("gfycat")

    gfycat_filename = "{category}_@{username} - {title[:160]} [{gfyId}].{extension}"

    """ configuring gfycat download properties """
    config.set(("extractor",), "gfycat", {
        "#": "use different directory and filename formats when coming from a reddit post",
        "directory": subdirectories,
        "filename": gfycat_filename
    })


# using yt-dl specifically for tiktok videos
def download_tiktok(url, path, include_subfolder):
    # call yt-dlp downloader

    output_directory = os.path.abspath(path)
    #TODO: Append any user specified subfolders to output_directory path
    if(include_subfolder):
        subfolder = os.path.dirname("./tiktok/")
        output_directory = os.path.abspath(os.path.join(path, subfolder))
    ydl_opts = {
        'logger': YTDLPLogger(),
        # 'progress_hooks': [my_hook],
        'outtmpl': f'{output_directory}/%(extractor)s_@%(uploader)s - %(title).120s... (%(track)s - %(artist)s) [%(id)s].%(ext)s'
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
        """ Following block of code not needed since gallery-dl by default creates a subfolder to categorize by websites"""
        # subfolder = os.path.dirname(f'./umm/')
        # if(include_subfolder):
        #     config.set(("extractor",), "base-directory", os.path.abspath(os.path.join(path, subfolder)))
        # else:
        #     config.set(("extractor",), "base-directory", os.path.abspath(path))

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
    return None


def gallery_dl_download(url):
    gallery_dl_dowbload_job = job.DownloadJob(url)
    gallery_dl_dowbload_job.run()

def gallery_dl_get_info(url):
    gallery_dl_data_job = job.DataJob(url)
    # gallery_dl_data_job.run()
    extracted_info = gallery_dl.extractor.find(url)
    for att in dir(extracted_info):
        print(att, getattr(extracted_info,att))
    for x in extracted_info:
        print(x)

def Convert(tup):
    dictionary = dict((key, value) for key, value in tup)

    # Return the completed dictionary
    return dictionary

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('PyCharm')

    args_obj = get_args()
    print(args_obj)
    arg_download_path = os.path.abspath(args_obj.path)
    include_domain_subfolder = args_obj.ds
    # set_up_gallery_dl(arg_download_path)   #(root_download_path)
    # num_of_args = len(argv)
    # parsed = json.dumps(gallery_dl_config.get("extractor", "base-directory"), indent=2 )
    # print(parsed)

    # if(num_of_args < 2):
    #     show_help()
    #     quit()

    # getting rid of the dirty queries
    # sanitized_url = remove_query_string(args_obj.url)

    parsed_url = urllib.parse.urlparse(args_obj.url)
    domain = parsed_url.netloc

    domains = ['*reddit.com', '*twitter.com', '*instagram.com', '*imgur.com', '*gfycat.com']
    print("Supported domains : " + str(domains))

    matched_domain = match_domain(args_obj.url, domains)
    print(matched_domain)
    if matched_domain:
        match matched_domain:
            case "reddit":
                config_reddit_download(arg_download_path, include_domain_subfolder)
                gallery_dl_download(args_obj.url)
            case "twitter":
                config_twitter_download(arg_download_path, include_domain_subfolder)
                gallery_dl_download(args_obj.url)
            case "instagram":
                config_instagram_download(arg_download_path, include_domain_subfolder)
                gallery_dl_download(args_obj.url)
                # gallery_dl_get_info(args_obj.url)
            case "imgur":
                config_imgur_download(arg_download_path, include_domain_subfolder)
                gallery_dl_download(args_obj.url)
            case "gfycat":
                config_gfycat_download(arg_download_path, include_domain_subfolder)
                gallery_dl_download(args_obj.url)
            case other:
                print("???")
    elif 'tiktok.com' in domain:
        print(f'> Using yt-dl for tiktok')
        download_tiktok(args_obj.url, arg_download_path, include_domain_subfolder)
    else:
        print(f'> Using generic fallback download method')
        download_yt_dlp_generic(args_obj.url, arg_download_path, include_domain_subfolder)

    # Check if string matches regex list
    # Using filter + fnmatch
    # supportedDomain = bool(list(filter(lambda x: fnmatch.fnmatch(domain, x), domains)))
    # print(list(filter(lambda x: fnmatch.fnmatch(domain, x), domains)))
    # print(supportedDomain)

    # if supportedDomain:
    #     print(f'> Using gallery-dl to download...')
    #     resss = job.DownloadJob(sanitized_url)
    #     resss.run()



    # get_post(remove_query_string(argv[1]))
    # for index, url in enumerate(reddit_post_urls):
    #     if num_of_args < 2:
    #         show_help()
    #     else:
    #         print(f">URL: {index+1}")
    #         get_post(remove_query_string(url), 'gif')
