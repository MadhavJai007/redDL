"""
This file will be used to store config settings that will allow user to personalize their experience according to their needs
"""

# Just to be safe, ensure that the root folder is a directory that does not require admin privileges to access it
# or you could just run redDL in admin mode
ROOT_DOWNLOADS_FOLDER = "D:/redDL"
USE_ROOT_FOLDER = False
REDDIT_DOWNLOAD_FOLDER = ""
TWITTER_DOWNLOAD_FOLDER = ""
TIKTOK_DOWNLOAD_FOLDER = ""
INSTAGRAM_DOWNLOAD_FOLDER = ""

# Rearrange the labels in the curly brackets "{ }" to modify the output name

""" Reddit variables """
# category = The platform its from (reddit, instagram, etc..)
# subreddit = the subreddit its from
# num = number assocaited with media. Used when there are more than two images in a post
# id = the  reddit post's id
REDDIT_OUTPUT_FORMATS = {
    "default": "reddit_{subreddit} {num:?//>02}. {title[:160]} [{id}].{extension}",
    "subreddit+title": "{subreddit} {num:?//>02}. {title[:160]}.{extension}",
    "subreddit+title+id": "{subreddit} {num:?//>02} [{id}]. {title[:160]}.{extension}"
}


# {
#     "seperator": "_",
#     "category": {
#         "desc": "simply puts 'reddit' in the file name if enabled",
#         "enabled": True,
#         "order": 1
#     },
#     "subreddit": {
#         "desc": "simply puts 'reddit' in the file name if enabled",
#         "enabled": True,
#         "order": 2
#     }
# }


