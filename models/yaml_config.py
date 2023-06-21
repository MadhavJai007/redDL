import yaml
import json
import os
import pathlib

""" Class that represents the yaml config's properties"""
class RedDLConfig:

    def __init__(self, main_arguments, file_output_names):
        self._root_dl_folder = self.check_path(main_arguments["rootDownloadFolder"])
        self._website_folder = self.check_if_bool(main_arguments["websiteSubfolder"])
        self._subreddit_folder = self.check_if_bool(main_arguments["subredditSubfolder"])
        self._multiple_media_folder = self.check_if_bool(main_arguments["multipleMediaSubfolder"])
        self._ig_stories_folder = self.check_if_bool(main_arguments["igStoriesSubfolder"])
        self._ig_highlights_folder = self.check_if_bool(main_arguments["igHighlightSubfolder"])
        self._ig_username_folder = self.check_if_bool(main_arguments["igUsernameSubfolder"])

        # file name properties
        self._reddit_filename = self.check_empty_str(file_output_names["redditOutputString"])
        self._twitter_filename = self.check_empty_str(file_output_names["twitterOutputString"])
        self._ig_highlight_filename = self.check_empty_str(file_output_names["instagramOutputStrings"]["highlights"])
        self._ig_story_filename = self.check_empty_str(file_output_names["instagramOutputStrings"]["story"])
        self._ig_post_filename = self.check_empty_str(file_output_names["instagramOutputStrings"]["posts"])
        self._tiktok_filename = self.check_empty_str(file_output_names["tiktokOutputString"])


    @property
    def root_dl_folder(self):
        return self._root_dl_folder

    @root_dl_folder.setter
    def root_dl_folder(self, value):
        raise WriteConfigAttrError(f"root_dl_folder is only read-only attribute")

    @property
    def website_folder(self ):
        return self._website_folder

    @property
    def subreddit_folder(self):
        return self._subreddit_folder

    @property
    def multiple_media_folder(self):
        return self._multiple_media_folder

    @property
    def ig_stories_folder(self):
        return self._ig_stories_folder

    @property
    def ig_highlights_folder(self):
        return self._ig_highlights_folder

    @property
    def ig_username_folder(self):
        return self._ig_username_folder


    ''' File name string properties'''
    @property
    def ig_highlight_filename(self):
        return self._ig_highlight_filename

    @property
    def ig_story_filename(self):
        return self._ig_story_filename

    @property
    def ig_post_filename(self):
        return self._ig_post_filename

    @property
    def reddit_filename(self):
        return self._reddit_filename

    @property
    def twitter_filename(self):
        return self._twitter_filename

    @property
    def tiktok_filename(self):
        return self._tiktok_filename


    # method to check if string is empty
    @staticmethod
    def check_empty_str(filename_string):
        if isinstance(filename_string, str):
            if filename_string.strip() == "":
                raise TypeError("File name in config is an empty string!")
            else:
                return filename_string
        else:
            raise TypeError("One of your defined file names is not a string")

    # method to check if value is booke
    @staticmethod
    def check_if_bool(supposed_bool):
        if isinstance(supposed_bool, bool):
            return supposed_bool
        else:
            raise TypeError("Not True or False in config")

    # validate if a path string is or could be useable
    @staticmethod
    def check_path(value):
        # check if the value is a potentially valid path
        if os.path.isdir(value):
            print("valid and present")
            return value
        elif os.access(os.path.dirname(value), os.W_OK):
            print("the download folder can be made here")
            return value
        else:
            print("Invalid directory path. Using a default path (./redDL)...")
            return "./redDL"

class WriteConfigAttrError(Exception):
    """Attribute cant be modifed"""
    # def __init__(self, attr_name):
    #     # self._attr_name = attr_name
    #     print(attr_name)
    pass
