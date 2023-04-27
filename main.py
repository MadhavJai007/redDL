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


# TODO: SPLIT INTO MORE FUNCTIONS AND MODULES

def generate_user_agent():
    # random user agent string
    # needed for accessing reddit post info
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'


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
