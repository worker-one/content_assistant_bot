import logging

from hydra.utils import instantiate
from omegaconf import OmegaConf
from PIL import Image
from telebot import TeleBot
from telebot.types import CallbackQuery

from content_assistant_bot.api.common import create_keyboard_markup, is_command
from content_assistant_bot.api.schemas import Message
from content_assistant_bot.core.llm import LLM
from content_assistant_bot.db import crud

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load config from config.strings.yaml
config = OmegaConf.load("./src/content_assistant_bot/conf/ideas.yaml")

def send_llm_response(
    bot: TeleBot,
    user_id: int,
    chat_history: list[Message],
    image: Image = None,
    reply_markup=None
    ) -> list[Message]:

    # Load configurations
    model_config = instantiate(config.llm)

    # Initialize the LLM model
    llm = LLM(model_config)

    # Generate and send the final response
    response = llm.run(chat_history, image=image)
    bot.send_message(
        user_id, response.response_content,
        reply_markup = reply_markup,
        parse_mode="Markdown"
    )
    response = response.response_content
    chat_history.append(
        Message(
            content=response,
            role="assistant"
        )
    )
    return chat_history


def generate_more_ideas(
    call: CallbackQuery,
    bot: TeleBot,
    chat_history: list[Message]
    ):
    del bot.callback_query_handlers[-1]
    chat_history.append(
        Message(
            content=config.strings.more_ideas.ru,
            role="user"
        )
    )
    chat_history = send_llm_response(
        bot, call.from_user.id, chat_history,
        reply_markup=create_keyboard_markup(["Меню"], ["_menu"])
    )


def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: "_generate_ideas" in call.data)
    def generate_ideas(call: CallbackQuery, data: dict):
        user = crud.get_user(username=call.from_user.username)

        # Ask user to enter the prompt
        sent_message = bot.send_message(
            call.from_user.id,
            config.strings.enter_query[user.lang],
            reply_markup=create_keyboard_markup(["Меню"], ["_menu"])
        )

        # Register next handler
        bot.register_next_step_handler(sent_message, invoke_llm)


    @bot.message_handler(
        func=lambda message: not is_command(message),
        content_types=["text"]
    )
    def invoke_llm(message):
        user_id = int(message.chat.id)
        user_message = message.text
        image = None

        # Truncate and add the message to the chat history
        user_message = user_message[:30000]
        chat_history = [
            Message(
                content=user_message,
                role="user"
            )
        ]

        more_ideas_button = create_keyboard_markup(
            [config.strings.more_ideas.ru, config.strings.main_menu.ru],
            ["_generate_more_ideas", "_menu"]
        )

        chat_history = send_llm_response(
            bot, user_id, chat_history, image,
            reply_markup=more_ideas_button
        )

        bot.register_callback_query_handler(
            lambda call: call.data in ["_generate_more_ideas"],
            lambda call: generate_more_ideas(
                call, bot, chat_history
            )
        )
