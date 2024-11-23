import logging
import os
import re
from datetime import datetime, timedelta

import pandas as pd
from omegaconf import OmegaConf
from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from content_assistant_bot.core.utils import format_excel_file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load config from config.common.yaml
config = OmegaConf.load("./src/content_assistant_bot/conf/config.yaml")
strings = OmegaConf.load("./src/content_assistant_bot/conf/common.yaml")


def is_command(message):
    """
    Checks if the message is a command (starts with '/').
    """
    return bool(message.text and message.text.startswith("/"))


def sanitize_instagram_input(user_input: str) -> str:
    user_input = user_input.replace("#", "").replace("@", "")
    if "instagram.com" in user_input:
        match = re.search(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)", user_input)
        if match:
            user_input = match.group(1)
    return user_input


def create_resource(user_id: int, name: str, data_list: list[dict]) -> str:
    # Create user directory
    user_dir = f"./tmp/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    cleanup_files(user_dir)

    # Sanitize name for filename
    sanitized_name = re.sub(r'[\/:*?"<>| ]', '_', name)[:15]

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{timestamp}_{sanitized_name}_ig.xlsx"
    filepath = os.path.join(user_dir, filename)

    # Create and save Excel file
    df = pd.DataFrame(data_list)
    df.to_excel(filepath, index=False)
    format_excel_file(filepath)

    return filename


# Utility: Cleanup old files
def cleanup_files(user_dir: str, retention_period: int = 2):
    now = datetime.now()
    for root, _, files in os.walk(user_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if now - file_creation_time > timedelta(days=retention_period):
                os.remove(file_path)
                logger.info(f"Deleted old file: {file_path}")


def create_cancel_button(strings, lang):
    cancel_button = InlineKeyboardMarkup(row_width=1)
    cancel_button.add(
        InlineKeyboardButton(strings.cancel[lang], callback_data="CANCEL"),
    )
    return cancel_button


def create_keyboard_markup(
    options: list[str],
    callback_data: list[str],
    orientation: str = "vertical",
    ) -> InlineKeyboardMarkup:
    if orientation == "horizontal":
        keyboard_markup = InlineKeyboardMarkup(row_width=len(options))
    elif orientation == "vertical":
        keyboard_markup = InlineKeyboardMarkup(row_width=1)
    else:
        raise ValueError("Invalid orientation value. Must be 'horizontal' or 'vertical'")
    buttons = [InlineKeyboardButton(option, callback_data=data) for option, data in zip(options, callback_data)]
    keyboard_markup.add(*buttons)
    return keyboard_markup


def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: call.data.startswith("GET"))
    def get_resource(call: CallbackQuery, data):
        """Download resource from user's folder"""
        user = data["user"]
        filename = call.data.split(" ")[1]
        file_path = os.path.join("./tmp", str(user.id), filename)
        logger.info(f"Requesting file: {file_path}")
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                bot.send_document(user.id, file, visible_file_name=filename)
        else:
            bot.answer_callback_query(call.id, strings.file_not_found[user.lang])

    @bot.callback_query_handler(func=lambda call: call.data == "CANCEL")
    def cancel_callback(call: CallbackQuery, data):
        """Cancel current operation"""
        user = data["user"]
        bot.send_message(call.message.chat.id, strings.cancelled[user.lang])
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)