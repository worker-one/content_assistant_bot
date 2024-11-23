import logging
import os
import pandas as pd
from dotenv import find_dotenv, load_dotenv
from omegaconf import OmegaConf
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext
from telebot.types import CallbackQuery, InputMediaVideo, Message

from content_assistant_bot.api.handlers.common import create_keyboard_markup, sanitize_instagram_input
from content_assistant_bot.core import instagram
from content_assistant_bot.db.crud import get_user

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

strings = OmegaConf.load("./src/content_assistant_bot/conf/common.yaml")
config = OmegaConf.load("./src/content_assistant_bot/conf/analyze_account.yaml")

load_dotenv(find_dotenv(usecwd=True))
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    raise ValueError("Instagram credentials not found in environment variables")

instagram_client = instagram.InstagramWrapper(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

# Define States
class AnalyzeAccountStates(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_number_of_videos = State()

def format_account_reel_response(
    idx: int,
    reel: dict[str, str],
    template: str,
    average_likes: float,
    average_comments: float
    ) -> str:

    likes_diff = int(reel["likes"] - average_likes)
    likes_comparative = (
        config.strings.comparative_less["ru"].format(value=f"{abs(likes_diff):,}".replace(",", " "))
        if likes_diff < 0 else
        config.strings.comparative_more["ru"].format(value=f"{likes_diff:,}".replace(",", " "))
    )

    comments_diff = int(reel["comments"] - average_comments)
    comments_comparative = (
        config.strings.comparative_less["ru"].format(value=f"{abs(comments_diff):,}".replace(",", " "))
        if comments_diff < 0 else
        config.strings.comparative_more["ru"].format(value=f"{comments_diff:,}".replace(",", " "))
    )

    reel_response = template.format(
        idx=idx,
        likes=f"{reel['likes']:,}".replace(",", " "),
        likes_comparative=likes_comparative,
        comments=f"{reel['comments']:,}".replace(",", " "),
        comments_comparative=comments_comparative,
        link=reel["link"],
        views=f"{reel['play_count']:,}".replace(",", " ")
    )
    return reel_response

# Handlers
def register_handlers(bot):
    @bot.callback_query_handler(func=lambda call: "_analyze_account" in call.data)
    def analyze_account(call: CallbackQuery, state: StateContext):
        user = get_user(username=call.from_user.username)
        state.set(AnalyzeAccountStates.waiting_for_nickname)
        bot.send_message(
            call.from_user.id,
            config.strings.enter_nickname[user.lang]
        )

    @bot.message_handler(state=AnalyzeAccountStates.waiting_for_nickname)
    def get_instagram_input(message: Message, state: StateContext):
        user = get_user(username=message.from_user.username)
        user_input = sanitize_instagram_input(message.text)

        # Save user input in state data
        state.add_data(user_input=user_input)

        bot.send_message(message.chat.id, config.strings.received[user.lang])

        if not instagram_client.user_exists(user_input):
            bot.send_message(message.chat.id, config.strings.no_found[user.lang])
            logger.info(f"Error fetching reels for account {user_input}")
            state.delete()
            return

        keyboard = create_keyboard_markup(["5", "10", "30"], ["5", "10", "30"], "horizontal")
        state.set(AnalyzeAccountStates.waiting_for_number_of_videos)
        bot.send_message(
            message.chat.id,
            config.strings.ask_number_videos[user.lang],
            reply_markup=keyboard
        )

    @bot.callback_query_handler(
        func=lambda call: call.data in ["5", "10", "30"],
        state=AnalyzeAccountStates.waiting_for_number_of_videos
    )
    def get_number_of_videos(call: CallbackQuery, state: StateContext):
        user = get_user(username=call.from_user.username)
        number_of_videos = int(call.data)

        # Retrieve user input from state data
        with state.data() as data:
            input_text = data['user_input']

        response = instagram_client.fetch_user_reels(input_text)

        if response["status"] == 200:
            reels_data = response["data"]
            reels_data.sort(key=lambda x: x["play_count"], reverse=True)

            logger.info(f"Found {len(reels_data)} reels for account {input_text}")

            result_ready_msg = config.strings.result_ready[user.lang].format(n=number_of_videos, nickname=input_text)
            bot.send_message(call.message.chat.id, result_ready_msg, parse_mode="HTML")

            response_template = config.strings.results[user.lang]

            # Compute average values for likes and comments
            average_likes = sum([reel["likes"] for reel in reels_data]) / len(reels_data)
            average_comments = sum([reel["comments"] for reel in reels_data]) / len(reels_data)

            reel_response_items = [
                format_account_reel_response(
                    idx + 1,
                    reel,
                    response_template,
                    average_likes,
                    average_comments
                )
                for idx, reel in enumerate(reels_data[:number_of_videos])
            ]

            data_list = [
                {
                    "Url": reel["link"],
                    "Likes": reel["likes"],
                    "Comments": reel["comments"],
                    "Views": reel["play_count"],
                    "Post Date": reel["post_date"].strftime("%Y-%m-%d %H:%M:%S"),
                    "ER %": reel["er"] * 100,
                    "Owner": f'@{reel["owner"]}',
                    "Caption": reel["caption_text"]
                }
                for reel in reels_data
            ]

            # Generate unique filename and directory
            filename = create_resource(user.id, input_text, data_list)

            # Send response and download button
            footer = config.strings.final_message["ru"].format(bot_name=bot.get_me().first_name)
            hr = "\n" + "—" * 20 + "\n"
            response_message = '\n'.join(reel_response_items) + hr + footer

            download_button = create_keyboard_markup(
                [config.strings.download_report["ru"]],
                [f"GET {filename}"],
            )
            bot.send_message(
                call.message.chat.id,
                response_message,
                parse_mode="HTML",
                reply_markup=download_button
            )

            # Optionally send media group
            media_elements = []
            for reel in reels_data[:3]:
                media_elements.append(
                    InputMediaVideo(media=str(reel["video_url"]), caption=reel["title"])
                )
            if media_elements:
                bot.send_media_group(
                    call.message.chat.id,
                    media_elements
                )

            state.delete()

        else:
            if response["status"] == 403:
                bot.send_message(call.message.chat.id, config.strings.private_account[user.lang])
            else:
                bot.send_message(call.message.chat.id, config.strings.error[user.lang])
            state.delete()
