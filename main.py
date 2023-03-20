# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import json
import os
import shutil
import subprocess
import yt_dlp
from bs4 import BeautifulSoup
import urllib.parse
from requests import get, exceptions
from sys import argv as command_line_args
from logger import YTDLPLogger

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


def get_post(url, post_type):

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

    """ Just a random testing block. Ignore."""
    if(r.status_code == 200):
        post_id = url[url.find('comments/') + 9:]
        post_id = f"t3_{post_id[:post_id.find('/')]}"
        print(post_id)

        """ pointless. just use the reddit ".json" api instead """
        soup = BeautifulSoup(r.text, 'lxml')
        # data is found within the script tag
        js_script = soup.find('script', id='data')
        print(js_script)

        """ testing how reddit hosted video can be changed to different resolution by changing the number in the url """
        dash_url = "https://v.redd.it/cz86d1csp6ma1/DASH_1080.mp4"
        # slicing out the portion of the url after the underscore that comes after the "DASH". This will be the "base" url for the reddit video
        dash_url = dash_url[:int(dash_url.find('DASH')) + 4]
        # you can then modify the base url to change the resolution property by appending "{resolution number}.mp4"
        resolution_height = 1080
        modified_res_url = f'{dash_url}_{720}.mp4'
        # the base url can also be used to access the audio portion of the video.
        # (Not all reddit videos have audio though. Check if it exists with a get request)
        audio_url = f'{dash_url}_audio.mp4'
        print(modified_res_url)
        print(audio_url)

        # json_obj_data = json.loads(js_script.text.replace('window.___r = ', ''))[:-1]
        #
        # title = json_obj_data['posts']['models'][post_id]['title']
        # title = title.replace(' ', '_')
        # dash_url = json_obj_data['posts']['models'][post_id]['media']['dashUrl']
        # height = json_obj_data['posts']['models'][post_id]['media']['height']
        # dash_url = dash_url[:int(dash_url.find('DASH')) + 4]
        # # the dash URL is the main URL we need to search for
        # # height is used to find the best quality of video available
        # video_url = f'{dash_url}_{height}.mp4'  # this URL will be used to download the video
        # audio_url = f'{dash_url}_audio.mp4'  # this URL will be used to download the audio part

        # print(video_url)
        # print(audio_url)


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
        #     # audio_url = 'https://v.redd.it/82k6r4c3alna1/HLSPlaylist.m3u8'.split('HLS')
        # audio_url[0] += 'HLS_AUDIO_160_K.aac'
        # print(audio_url)
    except json.decoder.JSONDecodeError:
        print('ERROR: Post not found')
        quit()

    """ determines the post type"""
    post_type = json_data["post_hint"] if "post_hint" in json_data else "gallery" if "is_gallery" in json_data else "text"
    print(f'> Post type: {post_type}')

    """
    if determined as text post, double check if thats actually true
    (for some reason, some reddit hosted videos dont have the post_hint attribute) 
    """
    if post_type == "text":
        print("is it really tho?")
        # check if the media attribute and reddit_video sub-attribute exists
        if 'reddit_video' in json_data['media']:
            print("It's not!")
            post_type = "hosted:video"
            print(f'> Confirmed as reddit video')
            print(f'> Post type: {post_type}')
        else:
            print("Yes its just a text post.")



        # except Exception as ex:
        #     template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        #     message = template.format(type(ex).__name__, ex.args)
        #     print(message)


    # TODO: Extract permalink attribute for output name configuration
    permalink = json_data["permalink"]
    # split so different parts of the url can be used later
    permalink_attr = permalink.split("/")
    print(permalink_attr)

    """ decide on action depending on post type"""
    match post_type:
        case "gallery":
            print("This is a gallery post")
            img_urls = get_gallery_data(json_data["gallery_data"], json_data["media_metadata"])
        case "text":
            print("This is a regular text post")
        case "image":
            print("This is an image post")
            result = download_img(json_data["url"], json_data["title"], json_data["subreddit"])
            print(result)
        case _:
            print("Regular media post. Downloading...")
            # call yt-dlp downloader
            ydl_opts = {
                'logger': YTDLPLogger(),
                'progress_hooks': [my_hook]
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # help(yt_dlp.YoutubeDL)
                ydl.download(url)
                # info = ydl.extract_info(url, download=False)
                # print(json.dumps(ydl.sanitize_info(info)))


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


# function to download image
def download_img(img_url, img_name, subreddit):
    response = get(img_url, stream = True)

    # getting the image type extension
    img_type = img_url.split(".")[-1]
    img_name = f'{subreddit}-{img_name}.{img_type}'

    # downloading image to disk
    if response.status_code == 200:
        with open(img_name, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        print('Image sucessfully Downloaded: ', img_name)
        return "Success"
    else:
        print("Couldn't retrieve the image!!")
        return "Fail"

# function to get the different image ids in the gallery and create downloadable links out of them
def get_gallery_data(gallery_data_obj, media_metadata_list):
    gallery_img_list = gallery_data_obj["items"]
    reddit_img_netloc = "https://i.redd.it/"
    direct_img_urls = []
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
        print(f'> {idx+1}. Outbound link: {outbound_url}')
        print(f'> {idx+1}. {reddit_img_netloc}{media_id}.{img_type}')
        direct_img_urls.append(f'{reddit_img_netloc}{img_id["media_id"]}.{img_type}')

    return direct_img_urls

def my_hook(d):
    if d['status'] == "downloading":
        if d.get('eta') is not None:
            print(f'> ETA: {d["_eta_str"]} || Speed: {d["_speed_str"]} || Downloaded: {d["_downloaded_bytes_str"]} || Progress: {d["_percent_str"]}')
    elif d['status'] == 'finished':
        print('Finished downloading, now post-processing...')
    elif d['status'] == 'error':
        print('Uh oh. Stinky!')

def show_help():
    print(f"""
        Usage : {os.path.basename(command_line_args[0])} <URL_TO_POST_WITH_VIDEO>
    """)

# Used to remove any query portion of the url before doing anything since it can cause problems later on.
def remove_query_string(url):
    queryIndex=url.find('?')
    if(queryIndex>=0):
        return url[:(url.find('?'))]
    return url

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('PyCharm')

    num_of_args = len(command_line_args)
    get_post(remove_query_string(command_line_args[1]), 'gif')
    # for index, url in enumerate(reddit_post_urls):
    #     if num_of_args < 2:
    #         show_help()
    #     else:
    #         print(f">URL: {index+1}")
    #         get_post(remove_query_string(url), 'gif')
