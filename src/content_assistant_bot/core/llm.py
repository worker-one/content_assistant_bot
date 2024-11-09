from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_fireworks import ChatFireworks
from langchain_openai import ChatOpenAI
from PIL.Image import Image

from content_assistant_bot.api.schemas import Message, ModelConfig, ModelResponse
from content_assistant_bot.core.files import image_to_base64


class LLM:
    def __init__(self, config: ModelConfig):  # noqa: D107
        self.config = config
        self.clients = {"openai": ChatOpenAI, "fireworksai": ChatFireworks}

    def update_config(self, config: ModelConfig) -> None:
        """Update the model configuration"""
        for attr in ["provider", "model_name", "max_tokens", "chat_history_limit", "temperature", "system_prompt" ,"stream"]:
            if getattr(config, attr) is not None:
                self.config.__setattr__(attr, getattr(config, attr))

    def run(
        self, chat_history: list[Message],
        config: Optional[ModelConfig] = None,
        image: Optional[Image] = None
    ) -> ModelResponse:
        """Run the model with the given chat history and configuration"""
        if config is None and self.config is not None:
            config = self.config
        else:
            raise ValueError("Model configuration is required")

        provider = config.provider
        if provider not in self.clients:
            raise ValueError(f"Invalid provider: {provider}. Available providers: {', '.join(self.clients.keys())}")

        client = self.clients[provider](
            model_name=config.model_name, max_tokens=config.max_tokens, temperature=config.temperature
        )

        chat_history = chat_history[-config.chat_history_limit :]
        role_message_map = {"user": HumanMessage, "assistant": AIMessage}
        messages = [
            role_message_map[message.role](content=[{"type": "text", "text": message.content}])
            for message in chat_history
            if message.role in role_message_map
        ]

        # Add system prompt if any
        if config.system_prompt:
            prompt_message = HumanMessage(
                    content=[{"type": "text", "text": config.system_prompt}],
            )
            messages = [prompt_message] + messages

        # Handle the image if provided
        if image:
            message = HumanMessage(content=[{"type": "text", "text": "Received the following image(s):"}])
            image_base64 = image_to_base64(image)
            message.content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                }
            )
            messages.append(message)

        if config.stream:
            return client.stream(messages)
        else:
            response = client.invoke(messages)
            return ModelResponse(response_content=response.content, config=config)
