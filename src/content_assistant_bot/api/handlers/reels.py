import logging
import os

import pandas as pd
from content_assistant_bot.api.common import create_keyboard_markup
from content_assistant_bot.core import instagram
from content_assistant_bot.core.utils import format_excel_file
from content_assistant_bot.db.crud import get_user
from content_assistant_bot.db.models import User
from omegaconf import OmegaConf
from telebot.types import CallbackQuery, Message

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

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
            value=abs(likes_diff)
        )
    else:
        likes_comparative = strings.analyze_account.comparative_more["ru"].format(
            value=likes_diff
        )

    comments_diff = int(reel["comments"] - average_comments)
    if comments_diff < 0:
        comments_comparative = strings.analyze_account.comparative_less["ru"].format(
            value=abs(comments_diff)
        )
    else:
        comments_comparative = strings.analyze_account.comparative_more["ru"].format(
            value=comments_diff
        )

    reel_response = template.format(
        likes=reel["likes"],
        likes_comparative=likes_comparative,
        comments=reel["comments"],
        comments_comparative=comments_comparative,
        link=reel["link"],
        views=reel["play_count"]
    )
    return reel_response


def format_hashtag_reel_response(reel: dict[str, str], template: str) -> str:
    reel_response = template.format(
        likes=reel["likes"],
        comments=reel["comments"],
        link=reel["link"],
        views=reel["play_count"]
    )
    return reel_response

def send_reels(call: CallbackQuery, bot, reels: list[dict[str, str]], response_template: str):
    logger.info("_next_n_videos handler")
    for reel in reels:
        response = format_hashtag_reel_response(reel, response_template)
        bot.send_message(
            call.message.chat.id,
            response
    )
    del bot.callback_query_handlers[-1]
    bot.send_message(
        call.message.chat.id,
        "Выберите действие:",
        reply_markup=create_keyboard_markup(
            ["Меню"],
            ["_menu"],
        )
    )

def get_number_of_videos(call: CallbackQuery, bot, user: User, input_text: str, mode: str):
    print(len(bot.callback_query_handlers))
    del bot.callback_query_handlers[-1]
    print(len(bot.callback_query_handlers))
    print(f"input_text: {input_text}", f"mode: {mode}")
    number_of_videos = int(call.data)
    received_msg = strings.analyze_account.received[user.lang] if mode == 'account' else strings.analyze_hashtag.received[user.lang]
    bot.send_message(call.message.chat.id, received_msg)

    if mode == 'account':
        response = instagram_client.fetch_user_reels(input_text)
    else:
        response = instagram_client.fetch_hashtag_reels(input_text, estimate_view_count=False)

    if response["status"] == 200:
        reels = response["data"]
        reels.sort(key=lambda x: x["play_count"], reverse=True)

        result_ready_msg = (strings.analyze_account.result_ready[user.lang].format(n=number_of_videos, nickname=input_text)
                            if mode == 'account' else
                            strings.analyze_hashtag.result_ready[user.lang].format(n=number_of_videos, hashtag=input_text))
        bot.send_message(call.message.chat.id, result_ready_msg)

        response_template = strings.analyze_account.results[user.lang] if mode == 'account' else strings.analyze_hashtag.results[user.lang]

        # Compute average values for likes and comments
        average_likes = sum([reel["likes"] for reel in reels])/len(reels)
        average_comments = sum([reel["comments"] for reel in reels])/len(reels)

        data = []
        for idx, reel in enumerate(reels):
            if idx < number_of_videos:
                if mode == "account":
                    reel_response = format_account_reel_response(
                        reel, response_template,
                        average_likes, average_comments
                    )
                elif mode == "hashtag":
                    reel_response = format_hashtag_reel_response(reel, response_template)
                else:
                    reel_response = "Error"
                bot.send_message(
                    call.message.chat.id,
                    reel_response
                )
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
        )

        # Delete the Excel file after sending it
        os.remove(filepath)

        if mode == "hashtag":

            bot.send_message(
                call.message.chat.id,
                "Выберите действие:",
                reply_markup=create_keyboard_markup(
                    [strings.analyze_hashtag.next_videos[user.lang], "Меню"],
                    ["_next_n_videos", "_menu"],
                )
            )
            bot.register_callback_query_handler(
                lambda call: call.data in ["_next_n_videos"],
                lambda call: send_reels(
                    call, bot, reels[number_of_videos:(number_of_videos+3)],
                    response_template
                )
            )

    elif response["status"] == 403 and mode == 'account':
        bot.send_message(call.message.chat.id, strings.analyze_account.private_account[user.lang])
    elif response["status"] == 404:
        no_found_msg = strings.analyze_account.no_found[user.lang] if mode == 'account' else strings.analyze_hashtag.no_found[user.lang]
        bot.send_message(call.message.chat.id, no_found_msg)
    else:
        error_msg = strings.analyze_account.error[user.lang] if mode == 'account' else strings.analyze_hashtag.error[user.lang]
        bot.send_message(call.message.chat.id, error_msg)


def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: "_analyze_hashtag" in call.data)
    def analyze_hashtag(call: CallbackQuery):
        user = get_user(username=call.from_user.username)
        sent_message = bot.send_message(call.from_user.id, strings.analyze_hashtag.enter_hashtag[user.lang])
        bot.register_next_step_handler(sent_message, get_instagram_input, user, 'hashtag')

    @bot.callback_query_handler(func=lambda call: "_analyze_account" in call.data)
    def analyze_account(call: CallbackQuery):
        user = get_user(username=call.from_user.username)
        sent_message = bot.send_message(call.from_user.id, strings.analyze_account.enter_nickname[user.lang])
        bot.register_next_step_handler(sent_message, get_instagram_input, user, 'account')

    def get_instagram_input(message: Message, user: User, mode: str):
        input_text = message.text.replace("@", "").replace("#", "")
        if "instagram.com" in input_text:
            input_text = input_text.strip('/').split('/')[-1]
        if mode == 'account':
            if not instagram_client.user_exists(input_text):
                bot.send_message(message.chat.id, strings.analyze_account.no_found[user.lang])
                return
        keyboard = create_keyboard_markup(["5", "10", "30"], ["5", "10", "30"], "vertical")

        prompt = strings.analyze_account.ask_number_videos[user.lang] if mode == 'account' else strings.analyze_hashtag.ask_number_videos[user.lang]
        bot.send_message(message.chat.id, prompt, reply_markup=keyboard)

        bot.register_callback_query_handler(
            func = lambda call: get_number_of_videos(call, bot, user, input_text, mode),
            callback = lambda call: call.data in ["5", "10", "30"]
        )
        bot.clear_step_handler_by_chat_id(message.chat.id)
