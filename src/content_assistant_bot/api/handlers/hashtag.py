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

# Logging Configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load Configurations
strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")
config = OmegaConf.load("./src/content_assistant_bot/conf/analyze_hashtag.yaml")

# Environment Variables
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    raise ValueError("Instagram credentials not found in environment variables")

instagram_client = instagram.InstagramWrapper(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

def format_hashtag_reel_response(idx: int, reel: dict[str, str], template: str) -> str:
    return template.format(
        idx=idx,
        likes=f"{reel['likes']:,}".replace(",", " "),
        comments=f"{reel['comments']:,}".replace(",", " "),
        link=reel["link"],
        views=f"{reel['play_count']:,}".replace(",", " ")
    )

def send_reels(call: CallbackQuery, bot, reels: list[dict[str, str]], response_template: str):
    if call.data != "_next_n_videos":
        return
    del bot.callback_query_handlers[-1]
    logger.info(f"Handling reels for data: {call.data}")
    response_items = [format_hashtag_reel_response(idx+1, reel, response_template) for idx, reel in enumerate(reels)]
    bot.send_message(call.message.chat.id, "\n".join(response_items), parse_mode="HTML")

def send_excel_document(bot, call: CallbackQuery, filepath: str, filename: str):
    if call.data != "_download_document":
        return
    del bot.callback_query_handlers[-1]
    logger.info(f"Sending Excel document for data: {call.data}")
    with open(filepath, 'rb') as file:
        bot.send_document(call.message.chat.id, file, visible_file_name=filename)
    os.remove(filepath)

def get_number_of_videos(call: CallbackQuery, bot, user: User, input_text: str, mode: str):
    del bot.callback_query_handlers[-1]
    logger.info(f"Input text: {input_text}, Mode: {mode}")
    number_of_videos = int(call.data)
    bot.send_message(call.message.chat.id, config.strings.received[user.lang])

    response = instagram_client.fetch_hashtag_reels(input_text, estimate_view_count=False)

    if response["status"] == 200:
        reels = sorted(response["data"], key=lambda x: x["play_count"], reverse=True)
        logger.info(f"Found {len(reels)} reels for hashtag {input_text}")

        bot.send_message(
            call.message.chat.id,
            config.strings.result_ready[user.lang].format(n=number_of_videos, hashtag=input_text),
            parse_mode="HTML"
        )

        reel_responses = [format_hashtag_reel_response(idx+1, reel, config.strings.results[user.lang])
                          for idx, reel in enumerate(reels[:number_of_videos])]
        data = [{
            "Url": reel["link"],
            'Likes': reel["likes"],
            'Comments': reel["comments"],
            'Views': reel["play_count"],
            "Post Date": reel["post_date"].strftime("%Y-%m-%d %H:%M:%S"),
            "ER %": reel["er"] * 100,
            "Owner": f'@{reel["owner"]}',
            "Caption": reel["caption_text"]
        } for reel in reels]

        footer = config.strings.final_message["ru"].format(bot_name=bot.get_me().first_name)
        response_message = '\n'.join(reel_responses) + "\n" + "—"*20 + "\n" + footer
        bot.send_message(call.message.chat.id, response_message, parse_mode="HTML")

        df = pd.DataFrame(data)
        filename = f"{input_text}_reels_data.xlsx"
        filepath = os.path.join("./tmp", filename)
        os.makedirs("./tmp", exist_ok=True)
        df.to_excel(filepath, index=False)
        format_excel_file(filepath)

        bot.send_message(
            call.message.chat.id,
            "Выберите действие:",
            reply_markup=create_keyboard_markup(
                [config.strings.download_report["ru"], config.strings.next_videos[user.lang], "Меню"],
                ["_download_document", "_next_n_videos", "_menu"],
            )
        )

        bot.register_callback_query_handler(
            lambda c: c.data == "_download_document",
            lambda c: send_excel_document(bot, c, filepath, filename)
        )
        bot.register_callback_query_handler(
            lambda c: c.data == "_next_n_videos",
            lambda c: send_reels(c, bot, reels[number_of_videos:number_of_videos+3], config.strings.results[user.lang])
        )
    elif response["status"] == 404:
        bot.send_message(call.message.chat.id, config.strings.no_found[user.lang])
    else:
        bot.send_message(call.message.chat.id, config.strings.error[user.lang])

def register_handlers(bot):
    @bot.callback_query_handler(func=lambda call: "_analyze_hashtag" in call.data)
    def analyze_hashtag(call: CallbackQuery):
        user = get_user(username=call.from_user.username)
        sent_message = bot.send_message(call.from_user.id, config.strings.enter_hashtag[user.lang])
        bot.register_next_step_handler(sent_message, lambda msg: get_instagram_input(msg, user, 'hashtag'))

    def get_instagram_input(message: Message, user: User, mode: str):
        user_input = sanitize_instagram_input(message.text)
        keyboard = create_keyboard_markup(["5", "10", "30"], ["5", "10", "30"], "horizontal")
        bot.send_message(message.chat.id, config.strings.ask_number_videos[user.lang], reply_markup=keyboard)
        bot.register_callback_query_handler(
            lambda call: call.data in ["5", "10", "30"],
            lambda call: get_number_of_videos(call, bot, user, user_input, mode)
        )