from ast import Call
import logging
from typing import Optional
from telebot.handler_backends import BaseMiddleware
from telebot.types import Message, CallbackQuery

from content_assistant_bot.db import crud

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class UserMessageMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.update_types = ['message']

    def pre_process(self, message: Message, data: dict):
        user = crud.upsert_user(
            id=message.from_user.id,
            name=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        crud.add_message(
            username=message.from_user.username,
            text=message.text
        )
        logger.info(f"User event: user: '{message.from_user.username}', message: '{message.text}'")
        data['user'] = user

    def post_process(self, message, data, exception):
        pass


class UserCallbackMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.update_types = ['callback_query']

    def pre_process(self, callback_query: CallbackQuery, data: dict):
        user = crud.upsert_user(
            id=callback_query.from_user.id,
            name=callback_query.from_user.username,
            first_name=callback_query.from_user.first_name,
            last_name=callback_query.from_user.last_name
        )
        crud.add_message(
            username=callback_query.from_user.username,
            text=callback_query.data
        )
        logger.info(f"User event: user: '{callback_query.from_user.username}', callback_data: '{callback_query.data}'")
        data['user'] = user

    def post_process(self, callback_query, data, exception):
        pass