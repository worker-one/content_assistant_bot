import io
import logging
import os

from hydra.utils import instantiate
from omegaconf import OmegaConf
from PIL import Image
from telebot.types import CallbackQuery
from content_assistant_bot.api.common import is_command, download_file, create_keyboard_markup
from content_assistant_bot.core.llm import LLM
from content_assistant_bot.db import crud
from content_assistant_bot.api.schemas import Message

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define constants
TEMP_DIR = "./.tmp/files"
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# Define logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# load config from strings.yaml
strings = OmegaConf.load("./src/content_assistant_bot/conf/strings.yaml")

def register_handlers(bot):
    # Define the command for invoking the chatbot
    @bot.callback_query_handler(func=lambda call: "_generate_ideas" in call.data)
    def generate_ideas(call: CallbackQuery, data: dict):
        user = crud.get_user(username=call.from_user.username)

        # Ask user to enter the prompt
        sent_message = bot.send_message(call.from_user.id, strings.generate_ideas.enter_query[user.lang])

        # Register next handler
        bot.register_next_step_handler(sent_message, invoke_llm)

    @bot.message_handler(
        func=lambda message: not is_command(message),
        content_types=["text", "photo", "document"]
    )
    def invoke_llm(message):
        user_id = int(message.chat.id)
        user_message = message.caption if message.caption else ""
        image = None

        if message.content_type in ["photo", "document"]:
            # Extract file information
            if message.content_type == "photo":
                file_info = message.photo[-1]
            else:  # "document"
                file_info = message.document

            file_id = file_info.file_id
            filename = getattr(file_info, "file_name", f"file_{file_id}")
            user_input_file_path = os.path.join(TEMP_DIR, str(user_id), filename)

            logger.info("User event", extra={"user_id": user_id, "user_message": user_message})

            # Ensure the directory exists
            os.makedirs(os.path.dirname(user_input_file_path), exist_ok=True)
            download_file(bot, file_id, user_input_file_path)

            # Validate file size before processing
            if os.path.getsize(user_input_file_path) > MAX_FILE_SIZE:
                bot.reply_to(message, f"File size exceeds the maximum allowed size of {MAX_FILE_SIZE_MB} MB.")
                return

            file_extension = filename.rsplit(".", 1)[-1].lower()

            try:
                if file_extension in ALLOWED_IMAGE_EXTENSIONS:
                    with open(user_input_file_path, "rb") as file_obj:
                        image_bytes = file_obj.read()
                        image = Image.open(io.BytesIO(image_bytes))
                else:
                    bot.reply_to(message, f"Unsupported file type: {file_extension}")
                    return
            except Exception as e:
                logger.error(f"Error processing file: {e}")
                bot.reply_to(message, "An error occurred while processing your file.")
                return
            finally:
                # Clean up temporary file
                if os.path.exists(user_input_file_path):
                    os.remove(user_input_file_path)
        elif message.content_type == "text":
            user_message = message.text
        else:
            bot.reply_to(message, "Unsupported content type.")
            return

        # Truncate and add the message to the chat history
        user_message = user_message[:10000]
        chat_history = [
            Message(
                content=user_message,
                role="user"
            )
        ]

        # Load configurations
        config_llm = OmegaConf.load("./src/content_assistant_bot/conf/llm.yaml")
        model_config = instantiate(config_llm.fireworksai_llama)

        # Initialize the LLM model
        llm = LLM(model_config)
        logger.info(f"Loaded LLM model with config: {model_config.dict()}")

        if llm.config.stream:
            # Inform the user about processing
            sent_msg = bot.send_message(message.chat.id, "...")
            accumulated_response = ""

            # Generate response and send chunks
            for idx, chunk in enumerate(llm.run(chat_history, image=image)):
                accumulated_response += chunk.content
                if idx % 20 == 0:
                    try:
                        bot.edit_message_text(
                            accumulated_response, chat_id=message.chat.id, message_id=sent_msg.message_id
                        )
                    except Exception as e:
                        logger.error(f"Failed to edit message: {e}")
                        continue
                if idx > 200:
                    continue
            bot.edit_message_text(
                accumulated_response, chat_id=message.chat.id,
                message_id=sent_msg.message_id
            )
        else:
            # Generate and send the final response
            response = llm.run(chat_history, image=image)
            bot.send_message(message.chat.id, response.response_content)

        more_ideas_button = create_keyboard_markup(strings.generate_ideas.options, ["_generate_ideas"])
        bot.send_message(
            message.chat.id,
            " ",
            reply_markup=more_ideas_button
        )
