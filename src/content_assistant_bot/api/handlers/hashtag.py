import logging
import os

import pandas as pd
from omegaconf import OmegaConf
from telebot.types import CallbackQuery, Message

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


def format_hashtag_reel_response(reel: dict[str, str], template: str) -> str:
    reel_response = template.format(
        likes=f"{reel['likes']:,}".replace(",", " "),
        comments=f"{reel['comments']:,}".replace(",", " "),
        link=reel["link"],
        views=f"{reel['play_count']:,}".replace(",", " ")
    )
    return reel_response

def send_reels(call: CallbackQuery, bot, reels: list[dict[str, str]], response_template: str):
    logger.info(f"_next_n_videos handler, data: {call.data}")
    del bot.callback_query_handlers[-1]
    for reel in reels:
        response = format_hashtag_reel_response(reel, response_template)
        bot.send_message(
            call.message.chat.id,
            response
    )
    bot.send_message(
        call.message.chat.id,
        "Выберите действие:",
        reply_markup=create_keyboard_markup(
            ["Меню"],
            ["_menu"],
        )
    )

def get_number_of_videos(call: CallbackQuery, bot, user: User, input_text: str, mode: str):
    del bot.callback_query_handlers[-1]
    print(f"input_text: {input_text}", f"mode: {mode}")
    number_of_videos = int(call.data)
    received_msg = strings.analyze_hashtag.received[user.lang]
    bot.send_message(call.message.chat.id, received_msg)

    response = instagram_client.fetch_hashtag_reels(input_text, estimate_view_count=False)

    if response["status"] == 200:
        reels = response["data"]
        reels.sort(key=lambda x: x["play_count"], reverse=True)

        logger.info(f"Found {len(reels)} reels for hashtag {input_text}")

        result_ready_msg = strings.analyze_hashtag.result_ready[user.lang].format(n=number_of_videos, hashtag=input_text)
        bot.send_message(call.message.chat.id, result_ready_msg)

        response_template = strings.analyze_hashtag.results[user.lang]

        data = []
        reel_response_items = []
        for idx, reel in enumerate(reels):
            if idx < number_of_videos:
                reel_response_items.append(
                    format_hashtag_reel_response(reel, response_template)
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

        bot.send_message(
            call.message.chat.id,
            '\n\n'.join(reel_response_items)
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
        )

        # Delete the Excel file after sending it
        os.remove(filepath)

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

    elif response["status"] == 404:
        bot.send_message(call.message.chat.id, strings.analyze_hashtag.no_found[user.lang])
    else:
        bot.send_message(call.message.chat.id, strings.analyze_hashtag.error[user.lang])


def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: "_analyze_hashtag" in call.data)
    def analyze_hashtag(call: CallbackQuery):
        user = get_user(username=call.from_user.username)
        sent_message = bot.send_message(call.from_user.id, strings.analyze_hashtag.enter_hashtag[user.lang])
        bot.register_next_step_handler(sent_message, get_instagram_input, user, 'hashtag')

    def get_instagram_input(message: Message, user: User, mode: str):
        user_input = sanitize_instagram_input(message.text)
        keyboard = create_keyboard_markup(["5", "10", "30"], ["5", "10", "30"], "horizontal")

        prompt = strings.analyze_hashtag.ask_number_videos[user.lang]
        bot.send_message(message.chat.id, prompt, reply_markup=keyboard)

        bot.register_callback_query_handler(
            func = lambda call: get_number_of_videos(call, bot, user, user_input, mode),
            callback = lambda call: call.data in ["5", "10", "30"]
        )
