# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import json
import os
import subprocess
import urllib.parse
from requests import get, exceptions
from sys import argv as command_line_args

""" 
IMPORTANT:
https://www.reddit.com/r/gaming/comments/11qi515/the_year_is_2007_summer_break_just_started_i_just/
is equivalent to
https://www.reddit.com/r/gaming/comments/11qi515
is equivalent to
https://www.reddit.com/comments/11qi515

Basically the subreddit and post title portion of the url is unnecessary
"""


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


def get_post(url, post_type):
    try:  # checks if link is valid
        r = get(
            url + '.json',
            headers={'User-agent': generate_user_agent()}
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
        post_type = json_data["post_hint"] if "post_hint" in json_data else "gallery" if "is_gallery" in json_data else "text"
        # print(f'> Post type: {post_type}')
        # print(f'> Is reddit media domain: {json_data["is_reddit_media_domain"]}')
        # audio_url = 'https://v.redd.it/82k6r4c3alna1/HLSPlaylist.m3u8'.split('HLS')
        # audio_url[0] += 'HLS_AUDIO_160_K.aac'
        # print(audio_url)
    except json.decoder.JSONDecodeError:
        print('ERROR: Post not found')
        quit()

    match post_type:
        case "gallery":
            print("This is a gallery post")
            get_gallery_data(json_data["gallery_data"])
        case "text":
            print("This is a regular text post")
        case _:
            print("Regular media post. Downloading...")
    ytdlp_command = [
        '.\yt-dlp.exe',
        '--list-formats',
        url
    ]
    # code from ytdlp source

    parsed_url = urllib.parse.urlparse(json_data['url'])
    print(parsed_url)

    # if subprocess.run(ytdlp_command).returncode == 0:
    #     print('yt-dlp ran succesfully')
    # else:
    #     print("it failed...")

    """
        possible values for "post_hint" attribute: 
        
        link  (only examples i've seen:  Imgur)
        image (for both regular imgs and gifs)
        hosted:video (reddit video)
        rich:video (external media embeds)
        
        
    """

    """ is_gallery attribute for gallery posts"""

def get_gallery_data(gallery_data_obj):
    gallery_img_list = gallery_data_obj["items"]
    reddit_img_netloc = "https://i.redd.it/"
    for idx, img_id in enumerate(gallery_img_list):
        print(f'> {idx+1}.{reddit_img_netloc}{img_id["media_id"]}.jpg')


def show_help():
    print(f"""
        Usage : {os.path.basename(command_line_args[0])} <URL_TO_POST_WITH_VIDEO>
    """)

def remove_query_string(url):
    queryIndex=url.find('?')
    if(queryIndex>=0):
        return url[:(url.find('?'))]
    return url

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('PyCharm')

    reddit_post_urls = [
        "https://www.reddit.com/r/playnite/comments/tbbnkp/special_k_helper_improve_using_special_k_with/",  # text post with non media link domain
        "https://www.reddit.com/r/GalaxyS20FE/comments/11qozwu/problems_with_the_tone_of_colors_my_new_phone_has",
        "https://www.reddit.com/r/GalaxyS20FE/comments/11q6e4o/got_a_clipon_lens_kit_with_15x_macro_and_it_works",
        "https://www.reddit.com/r/gaming/comments/11qi515/the_year_is_2007_summer_break_just_started_i_just",
        "https://www.reddit.com/r/gifs/comments/11ppfms/a_bismuth_crystal_i_would_like_to_share",

    ]
    num_of_args = len(command_line_args)
    for index, url in enumerate(reddit_post_urls):
        if num_of_args < 2:
            show_help()
        else:
            print(f">URL: {index+1}")
            get_post(remove_query_string(url), 'gif')
