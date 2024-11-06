## Telegram Bot Template

This is a simple template for creating a Telegram bot using Python. It uses the `pyTelegramBotAPI` library for interaction with Telegram's API and SQLAlchemy for database interactions. The bot logs messages, saves user details, and can be deployed using Docker.

## Structure

The project is structured as follows:

`main.py` - The main file that defines and runs the bot.

`service/` - The module that contains a class with services for the bot.

`conf/config.py` - The file that contains the configuration for the bot and the application.

`conf/logging_config.py` - The file that contains the configuration for the logging.

`api/telegram.py` - The file that handles interactions with the Telegram API.

`db/database.py` - The file that handles interactions with the PostgreSQL database.

`tests/` - The directory that contains the tests for the application.

`Dockerfile` - The file that defines the Docker container for this application.

## Setup

1. Clone this repository.
2. Create a `.env` file in the root directory and add your database connection string and bot token.
3. Install the dependencies with `pip install .`.
4. Run the bot with `python src/telegrab_bot/main.py`.

## Docker

To run this application in a Docker container, follow these steps:

1. Build the Docker image with `docker build -t telegram-bot .`.
2. Run the Docker container with `docker run -p 80:80 telegram-bot`.

## Examples of use

In branches to this repository, you can find examples of use of this template.