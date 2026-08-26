"""请求 ID 生成、校验与异步上下文传播。by AI.Coding"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token

from starlette.types import ASGIApp, Message, Receive, Scope, Send

X_REQUEST_ID = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z", re.ASCII)
_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def is_valid_request_id(value: str | None) -> bool:
    """判断客户端请求 ID 是否满足安全字符与长度边界。by AI.Coding"""
    return value is not None and _REQUEST_ID_PATTERN.fullmatch(value) is not None


def generate_request_id() -> str:
    """生成不依赖客户端输入的 UUID 请求 ID。by AI.Coding"""
    return str(uuid.uuid4())


def normalize_request_id(value: str | None) -> str:
    """透传合法请求 ID，否则生成新的安全值。by AI.Coding"""
    if value is not None and is_valid_request_id(value):
        return value
    return generate_request_id()


def get_request_id() -> str | None:
    """返回当前异步调用上下文中的请求 ID。by AI.Coding"""
    return _request_id_context.get()


def get_request_id_from_scope(scope: Scope) -> str:
    """从请求 state 或上下文读取 ID，并为极端路径提供兜底。by AI.Coding"""
    state = scope.get("state") or {}
    request_id = state.get("request_id") or get_request_id()
    return request_id if request_id is not None else generate_request_id()


class RequestContextMiddleware:
    """为所有 HTTP 响应注入请求 ID 并隔离异步上下文。by AI.Coding"""

    def __init__(self, app: ASGIApp) -> None:
        """保存下游 ASGI 应用。by AI.Coding"""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """建立请求上下文，并在响应开始时附加请求 ID。by AI.Coding"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_request_id = headers.get(b"x-request-id")
        client_request_id = (
            raw_request_id.decode("ascii", errors="strict")
            if raw_request_id is not None and raw_request_id.isascii()
            else None
        )
        request_id = normalize_request_id(client_request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        token: Token[str | None] = _request_id_context.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            """在不修改响应体的前提下追加请求 ID 响应头。by AI.Coding"""
            if message["type"] == "http.response.start":
                response_headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id_context.reset(token)
