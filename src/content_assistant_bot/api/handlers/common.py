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
strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")

def create_cancel_button(strings, lang):
    cancel_button = InlineKeyboardMarkup(row_width=1)
    cancel_button.add(
        InlineKeyboardButton(strings.cancel[lang], callback_data="_cancel"),
    )
    return cancel_button

# React to any text if not command
def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: call.data == "_cancel")
    def cancel_callback(call, user):
        bot.send_message(call.message.chat.id, strings.cancelled[user.lang])
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)