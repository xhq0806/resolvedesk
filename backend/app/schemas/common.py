"""通用 API 响应 Schema。by AI.Coding"""

from pydantic import BaseModel


class Message(BaseModel):
    """通用消息响应。by AI.Coding"""

    message: str
