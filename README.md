# Content Assistant Bot

## Setup

1. Clone this repository.
2. In `.env.example` set up variables:
    - `BOT_TOKEN` -- bot token obtain from BotFather
    - `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` -- username and password from instagran account
    - `FIREWORKS_API_KEY` -- API key from https://fireworks.ai
3. Rename: `.env.example` -> `.env`
3. Install the dependencies with `pip install -e .`.
4. Run the bot with `python src/content_assistant_bot/main.py`.


## Configuration

It is possible to configure each application in `src/content_assistant_bot/conf`

To configure ideas generation module:

1. Open `src/content_assistant_bot/conf/ideas.yaml`
2. Set up parameters:
    - `model_name` -- language model to use (see the list here: https://fireworks.ai/models?type=text).
    - `max_tokens` -- max number of tokens to generate for each call for a model: more token longer the response will be.
    - `temperature` -- It affects the variability and randomness of generated responses, a lower value (close to 0) produces more deterministic and   focused outputs. Conversely, a higher temperature value (e.g., 1.0 or above) introduces more diversity and creativity.
    - `system_prompt` -- initial prompt.