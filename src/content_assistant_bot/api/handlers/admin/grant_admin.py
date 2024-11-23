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
    )
    return menu_markup

def create_cancel_button(strings, lang):
    cancel_button = InlineKeyboardMarkup(row_width=1)
    cancel_button.add(
        InlineKeyboardButton(strings.cancel[lang], callback_data="_cancel"),
    )
    return cancel_button


# Function to send a scheduled message
def send_scheduled_message(bot, chat_id, message_text):
    bot.send_message(chat_id, message_text)


# React to any text if not command
def register_handlers(bot):
    logger.info("Registering grant admin handlers")
    @bot.callback_query_handler(func=lambda call: call.data == "_add_admin")
    def add_admin_handler(call, data):
        user = data["user"]
        # to complete
        sent_message = bot.send_message(user.id, strings.enter_username[user.lang])

        # Move to the next step: receiving the custom message
        bot.register_next_step_handler(sent_message, get_username, bot, user)

    def get_username(message, bot, user):
        admin_username = message.text

        # Send prompt to enter user id
        sent_message = bot.send_message(user.id, strings.enter_user_id[user.lang], reply_markup=create_cancel_button(strings, user.lang))

        # Move to the next step: receiving the custom message
        bot.register_next_step_handler(sent_message, get_user_id, bot, user, admin_username)

    def get_user_id(message, bot, user, admin_username):
        admin_user_id = message.text

        added_user = crud.upsert_user(id=admin_user_id, name=admin_username, role="admin")

        bot.send_message(
            user.id, strings.add_admin_confirm[user.lang].format(
                user_id=int(added_user.id), username=added_user.name)
        )
