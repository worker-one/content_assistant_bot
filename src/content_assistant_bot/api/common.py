import logging
import os

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_keyboard_markup(
    options: list[str],
    callback_data: list[str],
    orientation: str = "vertical",
    ) -> InlineKeyboardMarkup:
    if orientation == "horizontal":
        keyboard_markup = InlineKeyboardMarkup(row_width=len(options))
        print(f"orientation: {orientation}")
    elif orientation == "vertical":
        keyboard_markup = InlineKeyboardMarkup(row_width=1)
    else:
        raise ValueError("Invalid orientation value. Must be 'horizontal' or 'vertical'")
    buttons = [InlineKeyboardButton(option, callback_data=data) for option, data in zip(options, callback_data)]
    keyboard_markup.add(*buttons)
    return keyboard_markup


def download_file(bot, file_id: str, file_path: str) -> None:
    """
    Downloads a file from Telegram servers and saves it to the specified path.

    Args:
        bot: The Telegram bot instance.
        file_id: The unique identifier for the file to be downloaded.
        file_path: The local path where the downloaded file will be saved.
    """
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))
    with open(file_path, "wb") as file:
        file.write(downloaded_file)
    logger.info(msg="OS event", extra={"file_id": file_id, "file_path": file_path, "event": "download_file"})


def is_command(message):
    """
    Checks if the message is a command (starts with '/').
    """
    return bool(message.text and message.text.startswith("/"))


def parse_callback_data(data):
    """Parse callback data to extract chat ID and name."""
    parts = data.split("_")
    return int(parts[2]), parts[3]


def sanitize_instagram_input(user_input: str) -> str:
    user_input = user_input.replace("#", "").replace("@", "")
    if "instagram.com" in user_input:
        user_input = user_input.strip('/').split('/')[-1]
    return user_input
