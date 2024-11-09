import logging.config

from omegaconf import OmegaConf
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")


def create_main_menu_markup(options: dict, lang: str = "en"):
    menu_markup = InlineKeyboardMarkup(row_width=1)
    menu_markup.add(
        InlineKeyboardButton(options.analyze_account[lang], callback_data="_analyze_account"),
        InlineKeyboardButton(options.hashtag_or_query_analysis[lang], callback_data="_analyze_hashtag"),
        InlineKeyboardButton(options.video_idea_generation[lang], callback_data="_generate_ideas"),
        InlineKeyboardButton(options.subscription[lang], callback_data="_subscription")
    )
    return menu_markup


def register_handlers(bot):

    @bot.message_handler(commands=["start", "menu"])
    def menu_menu_command(message: Message, data: dict):
        #print(data)
        #user = data["user"]
        bot.send_message(
            message.chat.id, strings.menu.title["ru"],
            reply_markup=create_main_menu_markup(strings.menu.options, "ru")
        )

    @bot.callback_query_handler(func=lambda call: call.data == "_menu")
    def menu_menu_callback(call):
        bot.send_message(
            call.message.chat.id, strings.menu.title["ru"],
            reply_markup=create_main_menu_markup(strings.menu.options, "ru")
        )
