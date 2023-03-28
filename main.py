import json
import os
import shutil
import subprocess
import errno
import yt_dlp
from bs4 import BeautifulSoup
import gallery_dl
import urllib.parse
from requests import get, exceptions
from sys import argv
from logger import YTDLPLogger

# TODO: config settings
# Attempt to read any configuration settings
try:
    from user_config import ROOT_DOWNLOADS_FOLDER
    print(ROOT_DOWNLOADS_FOLDER)
except ImportError:
    print("Import config attempt failed!")
    print("Setting default values...")

gallery_dl_config = gallery_dl.config
gallery_dl_config.load()
gallery_dl_config.set(("extractor"), "base-directory", "D:/Gg/Media/")
gallery_dl_config.set("extractor", "reddit", {
			"#": "only spawn child extractors for links to specific sites",
            "whitelist": ["imgur", "redgifs", "gfycat"],

            "#": "put files from child extractors into the reddit directory",
            "parent-directory": True,

            "#": "transfer metadata to any child extractor as '_reddit'",
            "parent-metadata": "_reddit",
			"submission": {
				"directory": {
					"locals().get('is_gallery')": ["rddt_{subreddit} - {title[:160]} [{id}]"],
					""                          : []
				},
				"filename": {
					"locals().get('is_gallery')": "rddt_{subreddit} - {num:?//>02}. {title[:160]} [{id}].{extension}",
					"": "rddoot_{subreddit} - {title[:160]} [{id}].{extension}"
				}
			},
            "comments": 0,
            "morecomments": False,
            "date-min": 0,
            "date-max": 253402210800,
            "date-format": "%Y-%m-%dT%H:%M:%S",
            "id-min": None,
            "id-max": None,
            "recursion": 0,
            "videos": True
        })
gallery_dl_config.set("extractor", "imgur", {
			"#": "use different directory and filename formats when coming from a reddit post",
            "directory":
            {
                "'_reddit' in locals()": []
            },
            "filename":
            {
                "'_reddit' in locals()": "rddt_{_reddit[subreddit]} - {_reddit[title]} [{_reddit[id]}].{extension}",
                ""                     : "imgur_ {title} [{id}].{extension}"
            }
        })

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
    print(f"""
        Usage : {os.path.basename(argv[0])} <URL_TO_POST_WITH_VIDEO>
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

    num_of_args = len(argv)
    # parsed = json.dumps(gallery_dl_config.get("extractor", "base-directory"), indent=2 )
    # print(parsed)
    # resss = gallery_dl.job.UrlJob("https://imgur.com/a/g1RZCjG")
    # resss.run()
    get_post(remove_query_string(argv[1]))
    # for index, url in enumerate(reddit_post_urls):
    #     if num_of_args < 2:
    #         show_help()
    #     else:
    #         print(f">URL: {index+1}")
    #         get_post(remove_query_string(url), 'gif')
