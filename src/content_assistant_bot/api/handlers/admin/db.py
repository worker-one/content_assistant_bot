import logging
import logging.config
import os
from datetime import datetime

from omegaconf import OmegaConf

from content_assistant_bot.db import crud

config = OmegaConf.load("./src/content_assistant_bot/conf/config.yaml")
strings = OmegaConf.load("./src/content_assistant_bot/conf/common.yaml")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_handlers(bot):
    logger.info("Registering admin database handler")
    @bot.callback_query_handler(func=lambda call: call.data == "_export_data")
    def export_data_handler(call, data):
        user = data["user"]

        if user.role != "admin":
            # inform that the user does not have rights
            bot.send_message(call.from_user.id, strings.no_rights[user.lang])
            return

        # Export data
        tables = ['messages', 'users']
        export_dir = f'./data/{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        os.makedirs(export_dir)
        try:
            crud.export_all_tables(export_dir)
            for table in tables:
                # save as excel in temp folder and send to a user
                filename = f"{export_dir}/{table}.csv"
                bot.send_document(user.id, open(filename, 'rb'))
                # remove the file
                os.remove(filename)
        except Exception as e:
            bot.send_message(user.id, str(e))
            logger.error(f"Error exporting data: {e}")