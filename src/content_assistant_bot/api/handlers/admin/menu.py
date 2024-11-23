import logging
import logging.config
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from omegaconf import OmegaConf
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from content_assistant_bot.db import crud

config = OmegaConf.load("./src/content_assistant_bot/conf/config.yaml")
strings = OmegaConf.load("./src/content_assistant_bot/conf/common.yaml")

# Define Paris timezone
timezone = pytz.timezone(config.timezone)

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Dictionary to store user data during message scheduling
user_data = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_admin_menu_markup(strings, lang) -> InlineKeyboardMarkup:
    menu_markup = InlineKeyboardMarkup(row_width=1)
    menu_markup.add(
        InlineKeyboardButton(strings.admin_menu.send_message[lang], callback_data="_public_message"),
        InlineKeyboardButton(strings.admin_menu.add_admin[lang], callback_data="_add_admin"),
        InlineKeyboardButton(strings.admin_menu.export_data[lang], callback_data="_export_data"),
        InlineKeyboardButton(strings.admin_menu.about[lang], callback_data="_about"),
    )
    return menu_markup

# React to any text if not command
def register_handlers(bot):

    @bot.message_handler(commands=["admin"])
    def admin_menu_command(message: Message, data: dict):
        user = data["user"]
        print(user.__dict__)
        if user.role != "admin":
            # Inform the user that they do not have admin rights
            bot.send_message(message.from_user.id, strings.no_rights[user.lang])
            return

        # Send the admin menu
        bot.send_message(
            message.from_user.id, strings.admin_menu.title[user.lang],
            reply_markup=create_admin_menu_markup(strings, user.lang)
        )
