import logging
import logging.config
import os

import telebot
from dotenv import find_dotenv, load_dotenv
from omegaconf import OmegaConf

from telegram_bot.api.handlers import admin, audio, welcome
from telegram_bot.api.middlewares.antiflood import AntifloodMiddleware
from telegram_bot.api.middlewares.user import UserMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = OmegaConf.load("./src/telegram_bot/conf/config.yaml")

load_dotenv(find_dotenv(usecwd=True))  # Load environment variables from .env file
BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    logger.error(msg="BOT_TOKEN is not set in the environment variables.")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True)


def start_bot():
    logger.info(msg=f"Bot `{str(bot.get_me().username)}` has started")

    # handlers
    welcome.register_handlers(bot)
    audio.register_handlers(bot)
    admin.register_handlers(bot)

    # middlewares
    if config.antiflood.enabled:
        bot.setup_middleware(AntifloodMiddleware(bot, config.antiflood.time_window_seconds))
    bot.setup_middleware(UserMiddleware())

    # bot.infinity_polling()
    bot.polling()
