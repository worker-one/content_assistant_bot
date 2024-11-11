import logging
import os

import pandas as pd
from omegaconf import OmegaConf
from telebot.types import CallbackQuery, InputMediaVideo, Message

from content_assistant_bot.api.common import create_keyboard_markup, sanitize_instagram_input
from content_assistant_bot.core import instagram
from content_assistant_bot.core.utils import format_excel_file
from content_assistant_bot.db.crud import get_user
from content_assistant_bot.db.models import User


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    raise ValueError("Instagram credentials not found in environment variables")

instagram_client = instagram.InstagramWrapper(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

def format_account_reel_response(
    reel: dict[str, str],
    template: str,
    average_likes: float,
    average_comments: float
    ) -> str:

    likes_diff = int(reel["likes"] - average_likes)
    if likes_diff < 0:
        likes_comparative = strings.analyze_account.comparative_less["ru"].format(
            value=f"{abs(likes_diff):,}".replace(",", " ")
        )
    else:
        likes_comparative = strings.analyze_account.comparative_more["ru"].format(
            value=f"{likes_diff:,}".replace(",", " ")
        )

    comments_diff = int(reel["comments"] - average_comments)
    if comments_diff < 0:
        comments_comparative = strings.analyze_account.comparative_less["ru"].format(
            value=f"{abs(comments_diff):,}".replace(",", " ")
        )
    else:
        comments_comparative = strings.analyze_account.comparative_more["ru"].format(
            value=f"{comments_diff:,}".replace(",", " ")
        )

    reel_response = template.format(
        likes=f"{reel['likes']:,}".replace(",", " "),
        likes_comparative=likes_comparative,
        comments=f"{reel['comments']:,}".replace(",", " "),
        comments_comparative=comments_comparative,
        link=reel["link"],
        views=f"{reel['play_count']:,}".replace(",", " ")
    )
    return reel_response


def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: "_analyze_account" in call.data)
    def analyze_account(call: CallbackQuery):
        user = get_user(username=call.from_user.username)
        sent_message = bot.send_message(call.from_user.id, strings.analyze_account.enter_nickname[user.lang])
        bot.register_next_step_handler(sent_message, get_instagram_input, user, 'account')

    def get_instagram_input(message: Message, user: User, mode: str):
        user_input = sanitize_instagram_input(message.text)

        if not instagram_client.user_exists(user_input):
            bot.send_message(message.chat.id, strings.analyze_account.no_found[user.lang])
            logger.info(f"Error fetching reels for account {user_input}")

            # Ask user to write another nickname
            sent_message = bot.send_message(
                message.chat.id,
                strings.analyze_account.enter_nickname[user.lang],
                reply_markup=create_keyboard_markup(["Menu"], ["_menu"])
            )
            bot.register_next_step_handler(sent_message, get_instagram_input, user, 'account')
            return

        keyboard = create_keyboard_markup(["5", "10", "30"], ["5", "10", "30"], "horizontal")

        prompt = strings.analyze_account.ask_number_videos[user.lang]
        bot.send_message(message.chat.id, prompt, reply_markup=keyboard)

        bot.register_callback_query_handler(
            func = lambda call: get_number_of_videos(call, bot, user, user_input, mode),
            callback = lambda call: call.data in ["5", "10", "30"]
        )

    def get_number_of_videos(call: CallbackQuery, bot, user: User, input_text: str, mode: str):
        del bot.callback_query_handlers[-1]
        print(f"input_text: {input_text}", f"mode: {mode}")
        number_of_videos = int(call.data)
        received_msg = strings.analyze_account.received[user.lang]
        bot.send_message(call.message.chat.id, received_msg)

        response = instagram_client.fetch_user_reels(input_text)

        if response["status"] == 200:
            reels = response["data"]
            reels.sort(key=lambda x: x["play_count"], reverse=True)

            logger.info(f"Found {len(reels)} reels for account {input_text}")

            result_ready_msg = strings.analyze_account.result_ready[user.lang].format(n=number_of_videos, nickname=input_text)
            bot.send_message(call.message.chat.id, result_ready_msg)

            response_template = strings.analyze_account.results[user.lang]

            # Compute average values for likes and comments
            average_likes = sum([reel["likes"] for reel in reels])/len(reels)
            average_comments = sum([reel["comments"] for reel in reels])/len(reels)

            data = []
            reel_response_items = []
            for idx, reel in enumerate(reels):
                if idx < number_of_videos:
                    reel_response_items.append(format_account_reel_response(
                        reel, response_template,
                        average_likes, average_comments
                    ))
                    data.append({
                        "Url": reel["link"],
                        'Likes': reel["likes"],
                        'Comments': reel["comments"],
                        'Views': reel["play_count"],
                        "Post Date": reel["post_date"].strftime("%Y-%m-%d %H:%M:%S"),
                        "ER %": reel["er"]*100,
                        "Owner": f'@{reel["owner"]}',
                        "Caption": reel["caption_text"]
                    })
            # download the first three videos
            media_elements = []
            for reel in reels[:3]:
                media_elements.append(
                    InputMediaVideo(media=str(reel["video_url"]), caption=reel["title"])
                )
            bot.send_message(
                call.message.chat.id,
                '\n\n'.join(reel_response_items)
            )

            bot.send_media_group(
                call.message.chat.id,
                media_elements
            )


            # Save all data as a dataframe
            df = pd.DataFrame(data)
            filename = f"{input_text}_reels_data.xlsx"

            # check if tmp exists
            if not os.path.exists("./tmp"):
                os.makedirs("./tmp")
            filepath = os.path.join("./tmp", filename)  # Save it to a temporary directory
            df.to_excel(filepath, index=False)

            format_excel_file(filepath)

            # Send the Excel file to the user
            with open(filepath, 'rb') as file:
                bot.send_document(
                call.message.chat.id, file,
                visible_file_name = filename,
                caption = "Скачать отчёт",
                reply_markup=create_keyboard_markup(["Menu"], ["_menu"])
            )

            # Delete the Excel file after sending it
            os.remove(filepath)
        else:
            if response["status"] == 403:
                bot.send_message(call.message.chat.id, strings.analyze_account.private_account[user.lang])
            else:
                bot.send_message(call.message.chat.id, strings.analyze_account.error[user.lang])
