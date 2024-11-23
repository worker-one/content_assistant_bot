import logging
import os

from dotenv import find_dotenv, load_dotenv
from omegaconf import OmegaConf
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext
from telebot.types import CallbackQuery, Message

from content_assistant_bot.api.handlers.common import (
    create_keyboard_markup,
    create_resource,
    sanitize_instagram_input,
)
from content_assistant_bot.core import instagram
from content_assistant_bot.db.crud import get_user

# Logging Configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load Configurations
strings = OmegaConf.load("./src/content_assistant_bot/conf/common.yaml")
config = OmegaConf.load("./src/content_assistant_bot/conf/analyze_hashtag.yaml")

# Instagram Credentials
load_dotenv(find_dotenv(usecwd=True))
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    raise ValueError("Instagram credentials not found in environment variables")

instagram_client = instagram.InstagramWrapper(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)


# Define States
class AnalyzeHashtagStates(StatesGroup):
    waiting_for_hashtag = State()
    waiting_for_number_of_videos = State()
    showing_videos = State()


def format_hashtag_reel_response(idx: int, reel: dict[str, str], template: str) -> str:
    return template.format(
        idx=idx,
        likes=f"{reel['likes']:,}".replace(",", " "),
        comments=f"{reel['comments']:,}".replace(",", " "),
        link=reel["link"],
        views=f"{reel['play_count']:,}".replace(",", " "),
    )


# Handlers
def register_handlers(bot):
    # Start command handler
    @bot.callback_query_handler(func=lambda call: "_analyze_hashtag" in call.data)
    def analyze_hashtag(call: CallbackQuery, state: StateContext):
        user = get_user(username=call.from_user.username)
        state.set(AnalyzeHashtagStates.waiting_for_hashtag)
        bot.send_message(
            call.from_user.id,
            config.strings.enter_hashtag[user.lang],
        )

    # Handler for hashtag input
    @bot.message_handler(state=AnalyzeHashtagStates.waiting_for_hashtag)
    def get_instagram_input(message: Message, state: StateContext):
        user = get_user(username=message.from_user.username)
        user_input = sanitize_instagram_input(message.text)

        # Save user input in state data
        state.add_data(user_input=user_input)

        keyboard = create_keyboard_markup(
            ["5", "10", "30"],
            ["5", "10", "30"],
            "horizontal",
        )
        state.set(AnalyzeHashtagStates.waiting_for_number_of_videos)
        bot.send_message(
            message.chat.id,
            config.strings.ask_number_videos[user.lang],
            reply_markup=keyboard,
        )

    # Handler for number of videos selection
    @bot.callback_query_handler(
        func=lambda call: call.data in ["5", "10", "30"],
        state=AnalyzeHashtagStates.waiting_for_number_of_videos,
    )
    def get_number_of_videos(call: CallbackQuery, state: StateContext):
        user = get_user(username=call.from_user.username)
        number_of_videos = int(call.data)

        # Retrieve user input from state data
        with state.data() as data:
            input_text = data["user_input"]

        response = instagram_client.fetch_hashtag_reels(
            input_text, estimate_view_count=False
        )
        if response["status"] != 200:
            error_message = (
                strings.error[user.lang]
                if response["status"] != 404
                else strings.no_found[user.lang]
            )
            bot.send_message(call.message.chat.id, error_message)
            state.delete()
            return

        bot.send_message(
            call.message.chat.id,
            config.strings.result_ready[user.lang].format(
                n=number_of_videos, hashtag=input_text
            ),
            parse_mode="HTML",
        )

        reels_data = sorted(
            response["data"], key=lambda x: x["play_count"], reverse=True
        )

        # Format reel responses
        reel_response_items = [
            format_hashtag_reel_response(
                idx+1,
                reel,
                config.strings.results[user.lang],
            )
            for idx, reel in enumerate(reels_data[:number_of_videos])
        ]


        # Prepare data for excel file
        data_list = [
            {
                "Url": reel["link"],
                "Likes": reel["likes"],
                "Comments": reel["comments"],
                "Views": reel["play_count"],
                "Post Date": reel["post_date"].strftime("%Y-%m-%d %H:%M:%S"),
                "ER %": reel["er"] * 100,
                "Owner": f'@{reel["owner"]}',
                "Caption": reel["caption_text"],
            }
            for reel in reels_data[:number_of_videos]
        ]

        # Generate unique filename and directory
        filename = create_resource(user.id, data["user_input"], data_list)

        # Send response and download button
        footer = config.strings.final_message["ru"].format(bot_name=bot.get_me().username)
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

        # Save reels_data and current index in state
        state.add_data(
            reels_data=reels_data,
            current_index=0
        )

        # Send initial set of videos
        send_next_videos(call.message.chat.id, state, user)

    # Function to send next 3 videos
    def send_next_videos(chat_id: int, state: StateContext, user):
        with state.data() as data:
            reels_data = data["reels_data"]
            current_index = data["current_index"]

        # Calculate the next batch size
        batch_size = 3
        next_index = current_index + batch_size

        # Update current index in state
        with state.data() as data:
            data["current_index"] = next_index

        # Check if there are more videos to show
        if current_index == 0:
            # Show 'Show next 3 videos' button
            keyboard = create_keyboard_markup(
                [config.strings.show_next_videos[user.lang]],
                ["SHOW_NEXT_VIDEOS"],
            )
            bot.send_message(chat_id, config.strings.next_videos[user.lang], reply_markup=keyboard)

        elif next_index < len(reels_data):

            # Format reel responses
            reel_response_items = [
                format_hashtag_reel_response(
                    current_index+idx+1,
                    reel,
                    config.strings.results[user.lang],
                )
                for idx, reel in enumerate(reels_data[next_index:next_index+batch_size])
            ]

            response_message = '\n'.join(reel_response_items)
            bot.send_message(
                chat_id,
                response_message,
                parse_mode="HTML",
            )

        else:
            state.delete()

    # Handler for 'Show next 3 videos' button
    @bot.callback_query_handler(
        func=lambda call: call.data == "SHOW_NEXT_VIDEOS",
        state=AnalyzeHashtagStates.waiting_for_number_of_videos,
    )
    def show_next_videos(call: CallbackQuery, state: StateContext):
        user = get_user(username=call.from_user.username)
        send_next_videos(call.message.chat.id, state, user)
