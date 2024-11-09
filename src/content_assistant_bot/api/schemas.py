from typing import Optional

from pydantic import BaseModel


class Message(BaseModel):  # noqa: D101
    role: str
    content: str

class ModelConfig(BaseModel):  # noqa: D101
    model_name: Optional[str] = None
    provider: Optional[str] = None
    max_tokens: Optional[int] = None
    chat_history_limit: int = 10
    temperature: float = 0.5
    system_prompt: str = ""
    stream: Optional[bool] = True


class ModelResponse(BaseModel):  # noqa: D101
    response_content: str
    config: ModelConfig
