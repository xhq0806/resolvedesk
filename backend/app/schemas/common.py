"""通用 API 响应 Schema。by AI.Coding"""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """稳定且不暴露内部细节的错误响应。by AI.Coding"""

    code: str
    message: str
    request_id: str


class Message(BaseModel):
    """通用消息响应。by AI.Coding"""

    message: str
