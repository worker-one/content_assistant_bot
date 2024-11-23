import logging

from hydra.utils import instantiate
from omegaconf import OmegaConf
from PIL import Image
from telebot import types
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext

from content_assistant_bot.api.handlers.common import create_keyboard_markup
from content_assistant_bot.api.schemas import Message
from content_assistant_bot.core.llm import LLM
from content_assistant_bot.db import crud

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load config from config.common.yaml
config = OmegaConf.load("./src/content_assistant_bot/conf/ideas.yaml")

# Define States
class IdeasStates(StatesGroup):
    waiting_for_query = State()
    waiting_for_more_ideas = State()

# Handlers
def register_handlers(bot):

    @bot.callback_query_handler(func=lambda call: "_generate_ideas" in call.data)
    def generate_ideas(call: types.CallbackQuery, state: StateContext):
        user = crud.get_user(username=call.from_user.username)
        state.set(IdeasStates.waiting_for_query)
        bot.send_message(
            call.from_user.id,
            config.strings.enter_query[user.lang],
            reply_markup=create_keyboard_markup(["Меню"], ["_menu"])
        )

    @bot.message_handler(
        commands=["_generate_ideas", "idea"]
    )
    def generate_ideas(call: types.CallbackQuery, state: StateContext):
        user = crud.get_user(username=call.from_user.username)
        state.set(IdeasStates.waiting_for_query)
        bot.send_message(
            call.from_user.id,
            config.strings.enter_query[user.lang],
            reply_markup=create_keyboard_markup(["Меню"], ["_menu"])
        )

    @bot.message_handler(state=IdeasStates.waiting_for_query, content_types=['text'])
    def get_user_query(message: types.Message, state: StateContext):
        user_id = message.chat.id
        user_message = message.text

        # Truncate and add the message to the chat history
        user_message = user_message[:30000]
        chat_history = [
            Message(
                content=user_message,
                role="user"
            )
        ]

        # Send LLM response
        more_ideas_button = create_keyboard_markup(
            [config.strings.more_ideas.ru, config.strings.main_menu.ru],
            ["_generate_more_ideas", "_menu"]
        )

        chat_history = send_llm_response(
            bot, user_id, chat_history, reply_markup=more_ideas_button
        )

        # Store chat_history in state
        state.add_data(chat_history=chat_history)

        state.set(IdeasStates.waiting_for_more_ideas)

    @bot.callback_query_handler(func=lambda call: call.data == "_generate_more_ideas", state=IdeasStates.waiting_for_more_ideas)
    def generate_more_ideas(call: types.CallbackQuery, state: StateContext):
        user_id = call.from_user.id

        # Retrieve chat_history from state
        with state.data() as data:
            chat_history = data.get('chat_history', [])

        # Add the request for more ideas to the chat history
        chat_history.append(
            Message(
                content=config.strings.more_ideas.ru,
                role="user"
            )
        )

        # Send LLM response
        more_ideas_button = create_keyboard_markup(
            [config.strings.more_ideas.ru, config.strings.main_menu.ru],
            ["_generate_more_ideas", "_menu"]
        )

        chat_history = send_llm_response(
            bot, user_id, chat_history, reply_markup=more_ideas_button
        )

        # Update chat_history in state
        state.add_data(chat_history=chat_history)

def send_llm_response(
    bot,
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
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    response_content = response.response_content

    chat_history.append(
        Message(
            content=response_content,
            role="assistant"
        )
    )
    return chat_history
