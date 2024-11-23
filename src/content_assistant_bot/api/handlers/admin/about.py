"""Handler to show information about the bot's configuration."""
from omegaconf import OmegaConf

config = OmegaConf.load("./src/real_estate_telegram_bot/conf/config.yaml")

def register_handlers(bot):
    @bot.callback_query_handler(func=lambda call: call.data == "_about")
    def about_handler(call):
        user_id = call.from_user.id

        config_str = OmegaConf.to_yaml(config)

        # Send config
        bot.send_message(user_id, f"```yaml\n{config_str}\n```", parse_mode="Markdown")
