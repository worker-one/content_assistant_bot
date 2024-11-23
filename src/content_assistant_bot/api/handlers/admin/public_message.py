import logging
import logging.config
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from omegaconf import OmegaConf

from content_assistant_bot.api.handlers.common import create_cancel_button
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


# Function to send a scheduled message
def send_scheduled_message(bot, user_id, media_type, message_text: str = None, message_photo: str = None):
    if media_type == 'text':
        bot.send_message(chat_id=user_id, text=message_text)
    elif media_type == 'photo':
        # Fetch the photo by file ID
        if message_text:
            bot.send_photo(chat_id=user_id, caption=message_text, photo=message_photo, disable_notification=False)
        else:
            bot.send_photo(chat_id=user_id, photo=message_photo, disable_notification=False)


# React to any text if not command
def register_handlers(bot):
    logger.info("Registering public message handlers")
    @bot.callback_query_handler(func=lambda call: call.data == "_public_message")
    def query_handler(call, data):
        user = data["user"]

        if user.role != "admin":
            # Inform that the user does not have admin rights
            bot.send_message(user.id, strings.no_rights[user.lang])
            return

        # Ask user to provide the date and time
        sent_message = bot.send_message(
            user.id, strings.enter_datetime_prompt[user.lang].format(timezone=config.timezone),
            reply_markup=create_cancel_button(strings, user.lang)
        )
        # Move to the next step: receiving the datetime input
        bot.register_next_step_handler(sent_message, get_datetime_input, bot, user)

    # Handler to capture the datetime input from the user
    def get_datetime_input(message, bot, user):
        user_input = message.text
        try:
            # Parse the user's input into a datetime object
            user_datetime_obj = datetime.strptime(user_input, '%Y-%m-%d %H:%M')
            user_datetime_localized = timezone.localize(user_datetime_obj)

            # Check that date is not at the past
            if user_datetime_localized < datetime.now(timezone):
                bot.send_message(user.id, strings.past_datetime_error[user.lang])

                # Prompt the user again
                sent_message = bot.send_message(
                    user.id, strings.enter_datetime_prompt[user.lang].format(timezone=config.timezone),
                    reply_markup=create_cancel_button(strings, user.lang)
                )
                bot.register_next_step_handler(sent_message, get_datetime_input, bot, user)
                return

            # Store the datetime and move to the next step (waiting for the message content)
            user_data[user.id] = {'datetime': user_datetime_localized}
            sent_message = bot.send_message(user.id, strings.record_message_prompt[user.lang], reply_markup=create_cancel_button(strings, user.lang))

            # Move to the next step: receiving the custom message
            bot.register_next_step_handler(sent_message, get_message_content, bot, user)

        except ValueError:
            # Handle invalid date format
            sent_message = bot.send_message(user.id, strings.invalid_datetime_format[user.lang])
            # Prompt the user again
            sent_message = bot.send_message(
                user.id, strings.enter_datetime_prompt[user.lang].format(timezone=config.timezone),
                reply_markup=create_cancel_button(strings, user.lang)
            )
            bot.register_next_step_handler(sent_message, get_datetime_input, bot, user)

    # Handler to capture the custom message from the user
    def get_message_content(message, bot, user):
        user_message = None
        photo_file = None
        if message.text:
            user_message = message.text
            media_type = 'text'
        elif message.photo:
            # Get the highest quality image (last item in the list)
            photo_file = message.photo[-1].file_id
            user_message = message.caption
            media_type = 'photo'

        # Retrieve the previously stored datetime
        scheduled_datetime = user_data[user.id]['datetime']

        # Schedule the message for the specified datetime
        target_users = crud.get_users()
        for target_user in target_users:
            scheduler.add_job(
                send_scheduled_message, 'date',
                run_date=scheduled_datetime, 
                args=[bot, target_user.id, media_type, user_message, photo_file]
            )


        # Inform the user that the message has been scheduled
        response = strings.message_scheduled_confirmation[user.lang].format(
            n_users = len(target_users),
            send_datetime = scheduled_datetime.strftime('%Y-%m-%d %H:%M'),
            timezone = config.timezone
        )
        bot.send_message(user.id, response)

        # Clear the user data to avoid confusion
        del user_data[user.id]


# Start the scheduler
scheduler.start()
