"""稳定领域错误、异常映射与安全日志边界。by AI.Coding"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sentry_sdk.types import Event, Hint
from starlette import status

from app.core.request_context import X_REQUEST_ID, generate_request_id, get_request_id
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """前后端共享且保持稳定的领域错误码。by AI.Coding"""

    AUTH_REQUIRED = "AUTH_REQUIRED"
    USER_INACTIVE = "USER_INACTIVE"
    ROLE_FORBIDDEN = "ROLE_FORBIDDEN"
    TICKET_FORBIDDEN = "TICKET_FORBIDDEN"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    EMAIL_CONFLICT = "EMAIL_CONFLICT"
    TICKET_ALREADY_CLAIMED = "TICKET_ALREADY_CLAIMED"
    INVALID_ASSIGNEE = "INVALID_ASSIGNEE"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    TICKET_CLOSED = "TICKET_CLOSED"
    LAST_ACTIVE_ADMIN = "LAST_ACTIVE_ADMIN"
    DELETE_CONFIRMATION_REQUIRED = "DELETE_CONFIRMATION_REQUIRED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ErrorDefinition:
    """错误码对应的固定 HTTP 状态与安全公共文案。by AI.Coding"""

    status_code: int
    message: str


_ERROR_DEFINITIONS = MappingProxyType(
    {
        ErrorCode.AUTH_REQUIRED: ErrorDefinition(401, "Authentication is required."),
        ErrorCode.USER_INACTIVE: ErrorDefinition(403, "The user is inactive."),
        ErrorCode.ROLE_FORBIDDEN: ErrorDefinition(403, "The role is not allowed."),
        ErrorCode.TICKET_FORBIDDEN: ErrorDefinition(
            403, "The ticket operation is not allowed."
        ),
        ErrorCode.TICKET_NOT_FOUND: ErrorDefinition(404, "Ticket not found."),
        ErrorCode.USER_NOT_FOUND: ErrorDefinition(404, "User not found."),
        ErrorCode.EMAIL_CONFLICT: ErrorDefinition(409, "The email already exists."),
        ErrorCode.TICKET_ALREADY_CLAIMED: ErrorDefinition(
            409, "The ticket has already been claimed."
        ),
        ErrorCode.INVALID_ASSIGNEE: ErrorDefinition(409, "The assignee is invalid."),
        ErrorCode.INVALID_STATUS_TRANSITION: ErrorDefinition(
            409, "The status transition is invalid."
        ),
        ErrorCode.TICKET_CLOSED: ErrorDefinition(409, "The ticket is closed."),
        ErrorCode.LAST_ACTIVE_ADMIN: ErrorDefinition(
            409, "At least one active administrator is required."
        ),
        ErrorCode.DELETE_CONFIRMATION_REQUIRED: ErrorDefinition(
            409, "Delete confirmation is required."
        ),
        ErrorCode.VALIDATION_ERROR: ErrorDefinition(
            422, "The request validation failed."
        ),
        ErrorCode.INTERNAL_ERROR: ErrorDefinition(
            500, "An internal server error occurred."
        ),
    }
)


def get_error_definition(code: ErrorCode) -> ErrorDefinition:
    """返回错误码不可变的公开状态与文案定义。by AI.Coding"""
    return _ERROR_DEFINITIONS[code]


class AppError(Exception):
    """所有可安全返回给客户端的领域错误基类。by AI.Coding"""

    expected_status_code: int | None = None

    def __init__(self, code: ErrorCode) -> None:
        """按稳定错误码构造异常并校验子类状态约束。by AI.Coding"""
        definition = get_error_definition(code)
        if (
            self.expected_status_code is not None
            and definition.status_code != self.expected_status_code
        ):
            raise ValueError(
                f"{type(self).__name__} 不接受状态码 {definition.status_code} 的错误码。"
            )
        self.code = code
        self.status_code = definition.status_code
        self.message = definition.message
        super().__init__(code.value)


class NotFoundError(AppError):
    """资源不存在领域错误。by AI.Coding"""

    expected_status_code = status.HTTP_404_NOT_FOUND


class ForbiddenError(AppError):
    """角色或资源权限不足领域错误。by AI.Coding"""

    expected_status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    """资源状态冲突领域错误。by AI.Coding"""

    expected_status_code = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    """领域输入校验失败错误。by AI.Coding"""

    expected_status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


def log_application_error(
    *,
    error_code: ErrorCode,
    request_id: str | None = None,
    actor_role: str | None = None,
    resource_id: str | None = None,
) -> None:
    """仅使用白名单字段记录可诊断且不含正文的错误事件。by AI.Coding"""
    safe_request_id = request_id or get_request_id() or generate_request_id()
    extra: dict[str, str] = {
        "request_id": safe_request_id,
        "error_code": error_code.value,
    }
    if actor_role is not None:
        extra["actor_role"] = actor_role
    if resource_id is not None:
        extra["resource_id"] = resource_id
    logger.warning("application_error", extra=extra)


def _request_id(request: Request) -> str:
    """从请求 state 或上下文取得请求 ID，并提供安全兜底。by AI.Coding"""
    state_request_id = getattr(request.state, "request_id", None)
    return state_request_id or get_request_id() or generate_request_id()


def _error_response(
    *, request_id: str, code: ErrorCode, status_code: int
) -> JSONResponse:
    """创建 body 与响应头请求 ID 一致的错误响应。by AI.Coding"""
    definition = get_error_definition(code)
    payload = ErrorResponse(
        code=code.value,
        message=definition.message,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers={X_REQUEST_ID: request_id},
    )


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """将领域错误映射为稳定公开响应。by AI.Coding"""
    if not isinstance(exc, AppError):
        raise TypeError("AppError handler 收到不匹配的异常类型。")
    request_id = _request_id(request)
    log_application_error(error_code=exc.code, request_id=request_id)
    return _error_response(
        request_id=request_id,
        code=exc.code,
        status_code=exc.status_code,
    )


async def request_validation_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """隐藏原始输入，仅返回稳定校验错误响应。by AI.Coding"""
    if not isinstance(exc, RequestValidationError):
        raise TypeError("Validation handler 收到不匹配的异常类型。")
    request_id = _request_id(request)
    log_application_error(
        error_code=ErrorCode.VALIDATION_ERROR,
        request_id=request_id,
    )
    definition = get_error_definition(ErrorCode.VALIDATION_ERROR)
    return _error_response(
        request_id=request_id,
        code=ErrorCode.VALIDATION_ERROR,
        status_code=definition.status_code,
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """隐藏异常文本和堆栈，返回安全的内部错误响应。by AI.Coding"""
    del exc
    request_id = _request_id(request)
    log_application_error(error_code=ErrorCode.INTERNAL_ERROR, request_id=request_id)
    definition = get_error_definition(ErrorCode.INTERNAL_ERROR)
    return _error_response(
        request_id=request_id,
        code=ErrorCode.INTERNAL_ERROR,
        status_code=definition.status_code,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """为生产或测试 FastAPI 应用注册统一领域异常处理器。by AI.Coding"""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )
    app.add_exception_handler(
        Exception,
        internal_error_handler,
    )


def sanitize_sentry_event(event: Event, hint: Hint | None = None) -> Event:
    """移除 Sentry 事件中的请求数据、正文、局部变量和异常文本。by AI.Coding"""
    del hint
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("headers", "cookies", "query_string", "data", "env"):
            request.pop(key, None)

    event.pop("breadcrumbs", None)
    event.pop("extra", None)

    exception = event.get("exception")
    values = exception.get("values", []) if isinstance(exception, dict) else []
    for value in values:
        if not isinstance(value, dict):
            continue
        value.pop("value", None)
        stacktrace = value.get("stacktrace")
        frames = stacktrace.get("frames", []) if isinstance(stacktrace, dict) else []
        for frame in frames:
            if isinstance(frame, dict):
                frame.pop("vars", None)

    # 只保留已经由应用生成或验证的关联标签。
    tags = event.get("tags")
    if isinstance(tags, dict):
        event["tags"] = {
            key: value
            for key, value in tags.items()
            if key in {"request_id", "error_code"}
        }
    return event
