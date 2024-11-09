import logging
import random

from instagrapi import Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramWrapper:
    def __init__(self, login: str, password: str):
        if not login or not password:
            raise ValueError("Login and password are required")
        self.client = Client()
        if self.client.login(login, password):
            logger.info(f"Logged in as {login}")
        else:
            raise ValueError("Instagram client login failed")

    def user_exists(self, username: str):
        try:
            print(f"Username: {username}")
            self.client.user_id_from_username(username)
            return True
        except:
            False

    def fetch_user_reels(self, username: str, n_media_items: int = 40, estimate_view_count: bool = False):
        try:
            user_id = self.client.user_id_from_username(username)
        except:
            user_id = None
        print(f"user_id {user_id}")
        print(f"User ID: {user_id}")
        if not user_id:
            return {"status": 404, "message": "User not found"}
        user_info = self.client.user_info(user_id)
        if user_info.is_private:
            return {"status": 403, "message": "Account is private"}
        media_list = self.client.user_clips(user_id, amount=n_media_items)
        if not media_list:
            return {"status": 402, "message": "No reels found"}
        reels = []
        for media in media_list:
            if media.media_type == 2:
                if media.play_count != 0:
                    er = (media.like_count + media.comment_count) / media.play_count
                else:
                    er = 0
                reel_item = {
                    "title": media.title,
                    "caption_text": media.caption_text,
                    "likes": media.like_count,
                    "comments": media.comment_count,
                    "post_date": media.taken_at,
                    "link": f"https://www.instagram.com/reel/{media.code}/",
                    "play_count": media.play_count,
                    "id": media.id,
                    "er": er,
                    "owner": username,
                }
                if estimate_view_count:
                    reel_item["estimated_view_count"] = reel_item["likes"] * 100 + random.randint(100, 1000)
                reels.append(reel_item)
        return {"status": 200, "data": reels}

    def fetch_hashtag_reels(self, hashtag: str, n_media_items: int = 50, estimate_view_count: bool = False):
        media_list = self.client.hashtag_medias_top(hashtag, amount=n_media_items)
        print(len(media_list))
        if not media_list:
            return {"status": 404, "message": "Hashtag not found"}
        reels = []
        for media in media_list:
            if media.media_type == 2:
                if media.play_count != 0:
                    er = (media.like_count + media.comment_count) / media.play_count
                else:
                    er = 0
                reel_item = {
                    "title": media.title,
                    "caption_text": media.caption_text,
                    "likes": media.like_count,
                    "comments": media.comment_count,
                    "post_date": media.taken_at,
                    "link": f"https://www.instagram.com/reel/{media.code}/",
                    "play_count": media.play_count,
                    "id": media.id,
                    "er": er,
                    "owner": media.user.username
                }
                if estimate_view_count:
                    reel_item["estimated_view_count"] = reel_item["likes"] * 100 + random.randint(100, 1000)
                reels.append(reel_item)
        return {"status": 200, "data": reels}