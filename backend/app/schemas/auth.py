"""认证与密码安全 API Schema。by AI.Coding"""

from pydantic import BaseModel, ConfigDict, Field


class StrictInput(BaseModel):
    """拒绝未声明字段的认证输入基类。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class Token(BaseModel):
    """访问令牌响应。by AI.Coding"""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT 解码载荷；保留现有 sub 可选语义。by AI.Coding"""

    sub: str | None = None


class NewPassword(StrictInput):
    """密码重置请求。by AI.Coding"""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdatePassword(StrictInput):
    """当前用户修改密码请求。by AI.Coding"""

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
