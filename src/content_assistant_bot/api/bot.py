import logging
import logging.config
import os

import telebot
from dotenv import find_dotenv, load_dotenv
from omegaconf import OmegaConf

from content_assistant_bot.api.handlers import admin, audio, ideas, menu, reels
from content_assistant_bot.api.middlewares.antiflood import AntifloodMiddleware
from content_assistant_bot.api.middlewares.user import UserCallbackMiddleware, UserMessageMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = OmegaConf.load("./src/content_assistant_bot/conf/config.yaml")

load_dotenv(find_dotenv(usecwd=True))  # Load environment variables from .env file
BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    logger.error(msg="BOT_TOKEN is not set in the environment variables.")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True)


def start_bot():
    logger.info(msg=f"Bot `{str(bot.get_me().username)}` has started")

    # Handlers
    reels.register_handlers(bot)
    menu.register_handlers(bot)
    audio.register_handlers(bot)
    admin.register_handlers(bot)
    #ideas.register_handlers(bot)

    # Middlewares
    if config.antiflood.enabled:
        bot.setup_middleware(AntifloodMiddleware(bot, config.antiflood.time_window_seconds))
    bot.setup_middleware(UserMessageMiddleware())
    bot.setup_middleware(UserCallbackMiddleware())

    bot.infinity_polling()
    # bot.polling()
