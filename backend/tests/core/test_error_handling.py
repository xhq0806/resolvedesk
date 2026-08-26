"""验证领域错误、request_id 与安全日志基础设施。by AI.Coding"""

from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    get_error_definition,
    register_exception_handlers,
    sanitize_sentry_event,
)
from app.core.errors import (
    ValidationError as DomainValidationError,
)
from app.core.request_context import (
    X_REQUEST_ID,
    RequestContextMiddleware,
    get_request_id,
)
from app.schemas.common import ErrorResponse


class SecretPayload(BaseModel):
    """用于验证校验错误不回显敏感输入的测试请求。by AI.Coding"""

    password: str = Field(min_length=20)


def create_test_app() -> FastAPI:
    """创建只在本测试模块使用的错误处理应用。by AI.Coding"""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/success")
    def success() -> dict[str, str]:
        """返回正常响应并暴露当前上下文 ID 供一致性验证。by AI.Coding"""
        return {"request_id": get_request_id() or ""}

    @app.get("/legacy-error")
    def legacy_error() -> None:
        """模拟尚未迁移到领域错误的旧 HTTPException。by AI.Coding"""
        raise HTTPException(status_code=404, detail="legacy detail")

    @app.get("/domain/{error_code}")
    def domain_error(error_code: ErrorCode) -> None:
        """按测试输入触发对应领域错误。by AI.Coding"""
        definition = get_error_definition(error_code)
        error_type: type[AppError]
        if definition.status_code == 404:
            error_type = NotFoundError
        elif definition.status_code == 403:
            error_type = ForbiddenError
        elif definition.status_code == 409:
            error_type = ConflictError
        elif definition.status_code == 422:
            error_type = DomainValidationError
        else:
            error_type = AppError
        raise error_type(error_code)

    @app.post("/validation")
    def validation(payload: SecretPayload) -> dict[str, str]:
        """提供可控的 Pydantic 请求校验入口。by AI.Coding"""
        return {"password": payload.password}

    @app.get("/internal-error")
    def internal_error() -> None:
        """触发带敏感哨兵的未知异常。by AI.Coding"""
        raise RuntimeError(
            "jwt-sentinel password-sentinel message-sentinel "
            "internal-note-sentinel sql-sentinel"
        )

    @app.get("/context-after-yield")
    async def context_after_yield() -> dict[str, str]:
        """在异步调度点后读取 ContextVar。by AI.Coding"""
        await asyncio.sleep(0)
        return {"request_id": get_request_id() or ""}

    return app


def test_error_codes_match_design_statuses() -> None:
    """全部稳定错误码应映射到设计规定的 HTTP 状态。by AI.Coding"""
    expected_statuses = {
        ErrorCode.AUTH_REQUIRED: 401,
        ErrorCode.USER_INACTIVE: 403,
        ErrorCode.ROLE_FORBIDDEN: 403,
        ErrorCode.TICKET_FORBIDDEN: 403,
        ErrorCode.TICKET_NOT_FOUND: 404,
        ErrorCode.USER_NOT_FOUND: 404,
        ErrorCode.EMAIL_CONFLICT: 409,
        ErrorCode.TICKET_ALREADY_CLAIMED: 409,
        ErrorCode.INVALID_ASSIGNEE: 409,
        ErrorCode.INVALID_STATUS_TRANSITION: 409,
        ErrorCode.TICKET_CLOSED: 409,
        ErrorCode.LAST_ACTIVE_ADMIN: 409,
        ErrorCode.DELETE_CONFIRMATION_REQUIRED: 409,
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.INTERNAL_ERROR: 500,
    }

    assert set(expected_statuses) == set(ErrorCode)
    for code, status_code in expected_statuses.items():
        definition = get_error_definition(code)
        assert definition.status_code == status_code
        assert definition.message


def test_specialized_errors_reject_wrong_status_category() -> None:
    """专用异常不得接受其他 HTTP 类别的错误码。by AI.Coding"""
    with pytest.raises(ValueError):
        NotFoundError(ErrorCode.EMAIL_CONFLICT)
    with pytest.raises(ValueError):
        ForbiddenError(ErrorCode.TICKET_NOT_FOUND)
    with pytest.raises(ValueError):
        ConflictError(ErrorCode.ROLE_FORBIDDEN)
    with pytest.raises(ValueError):
        DomainValidationError(ErrorCode.INTERNAL_ERROR)


def test_error_response_has_exact_public_fields() -> None:
    """错误响应不得扩展调试信息或原始校验详情。by AI.Coding"""
    assert set(ErrorResponse.model_fields) == {"code", "message", "request_id"}


def test_request_id_is_generated_and_propagated() -> None:
    """缺少客户端 ID 时应生成 UUID，并在上下文和响应头保持一致。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        response = client.get("/success")

    request_id = response.headers[X_REQUEST_ID]
    assert uuid.UUID(request_id)
    assert response.json()["request_id"] == request_id
    assert get_request_id() is None


@pytest.mark.parametrize(
    "request_id",
    ["client-123", "trace.id_01:span-2", "A" * 64],
)
def test_valid_client_request_id_is_preserved(request_id: str) -> None:
    """合法客户端 ID 应原样透传。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        response = client.get("/success", headers={X_REQUEST_ID: request_id})

    assert response.headers[X_REQUEST_ID] == request_id
    assert response.json()["request_id"] == request_id


@pytest.mark.parametrize(
    "request_id",
    ["", "has space", "slash/value", "A" * 65, "tab\tvalue"],
)
def test_invalid_client_request_id_is_replaced(request_id: str) -> None:
    """不安全客户端 ID 应被 UUID 替换且不得反射。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        response = client.get("/success", headers={X_REQUEST_ID: request_id})

    generated = response.headers[X_REQUEST_ID]
    assert uuid.UUID(generated)
    assert generated != request_id


def test_legacy_http_exception_keeps_default_body() -> None:
    """旧 HTTPException body 应保持兼容，同时获得请求 ID 响应头。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        response = client.get("/legacy-error", headers={X_REQUEST_ID: "legacy-1"})

    assert response.status_code == 404
    assert response.json() == {"detail": "legacy detail"}
    assert response.headers[X_REQUEST_ID] == "legacy-1"


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        (ErrorCode.TICKET_NOT_FOUND, 404),
        (ErrorCode.ROLE_FORBIDDEN, 403),
        (ErrorCode.EMAIL_CONFLICT, 409),
        (ErrorCode.VALIDATION_ERROR, 422),
    ],
)
def test_domain_errors_have_stable_contract(code: ErrorCode, status_code: int) -> None:
    """领域错误响应应固定状态、错误码、文案和请求 ID。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        response = client.get(
            f"/domain/{code.value}", headers={X_REQUEST_ID: "domain-1"}
        )

    assert response.status_code == status_code
    assert response.json() == {
        "code": code.value,
        "message": get_error_definition(code).message,
        "request_id": "domain-1",
    }
    assert response.headers[X_REQUEST_ID] == "domain-1"


def test_validation_error_hides_sensitive_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """请求校验响应与日志不得包含提交的密码哨兵。by AI.Coding"""
    secret = "password-sentinel"
    with (
        caplog.at_level(logging.WARNING, logger="app.core.errors"),
        TestClient(create_test_app()) as client,
    ):
        response = client.post(
            "/validation",
            json={"password": secret},
            headers={X_REQUEST_ID: "validation-1"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": ErrorCode.VALIDATION_ERROR.value,
        "message": get_error_definition(ErrorCode.VALIDATION_ERROR).message,
        "request_id": "validation-1",
    }
    assert secret not in response.text
    assert all(secret not in record.getMessage() for record in caplog.records)


def test_internal_error_hides_exception_and_logs_only_safe_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """未知异常不得在响应或日志泄漏正文、SQL 或凭据。by AI.Coding"""
    sentinels = (
        "jwt-sentinel",
        "password-sentinel",
        "message-sentinel",
        "internal-note-sentinel",
        "sql-sentinel",
    )
    app = create_test_app()
    with (
        caplog.at_level(logging.WARNING, logger="app.core.errors"),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get(
            "/internal-error",
            headers={
                X_REQUEST_ID: "internal-1",
                "Authorization": "Bearer jwt-sentinel",
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "code": ErrorCode.INTERNAL_ERROR.value,
        "message": get_error_definition(ErrorCode.INTERNAL_ERROR).message,
        "request_id": "internal-1",
    }
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    for sentinel in sentinels:
        assert sentinel not in response.text
        assert sentinel not in combined_logs
    error_record = next(
        record
        for record in caplog.records
        if getattr(record, "error_code", None) == ErrorCode.INTERNAL_ERROR.value
    )
    assert error_record.request_id == "internal-1"
    assert not hasattr(error_record, "authorization")
    assert not hasattr(error_record, "body")


def test_context_ids_do_not_leak_between_requests() -> None:
    """连续异步请求应分别读取自己的请求 ID。by AI.Coding"""
    with TestClient(create_test_app()) as client:
        first = client.get(
            "/context-after-yield", headers={X_REQUEST_ID: "request-first"}
        )
        second = client.get(
            "/context-after-yield", headers={X_REQUEST_ID: "request-second"}
        )

    assert first.json()["request_id"] == "request-first"
    assert second.json()["request_id"] == "request-second"
    assert get_request_id() is None


def test_sentry_event_sanitizer_removes_sensitive_data() -> None:
    """Sentry 清洗函数应删除请求、面包屑、extra、局部变量和异常文本。by AI.Coding"""
    event = {
        "request": {
            "url": "https://example.test/api/v1/tickets",
            "headers": {"Authorization": "Bearer jwt-sentinel"},
            "cookies": {"session": "cookie-sentinel"},
            "query_string": "token=query-sentinel",
            "data": {"password": "password-sentinel"},
            "env": {"REMOTE_ADDR": "127.0.0.1"},
        },
        "breadcrumbs": {"values": [{"message": "message-sentinel"}]},
        "extra": {"internal_note": "internal-note-sentinel"},
        "tags": {
            "request_id": "request-safe",
            "error_code": "INTERNAL_ERROR",
            "unsafe": "drop-me",
        },
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "sql-sentinel",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "service.py",
                                "function": "run",
                                "lineno": 10,
                                "vars": {"password": "password-sentinel"},
                            }
                        ]
                    },
                }
            ]
        },
    }

    sanitized = sanitize_sentry_event(event)

    assert sanitized["request"] == {"url": "https://example.test/api/v1/tickets"}
    assert "breadcrumbs" not in sanitized
    assert "extra" not in sanitized
    assert sanitized["tags"] == {
        "request_id": "request-safe",
        "error_code": "INTERNAL_ERROR",
    }
    exception_value = sanitized["exception"]["values"][0]
    assert exception_value["type"] == "RuntimeError"
    assert "value" not in exception_value
    frame = exception_value["stacktrace"]["frames"][0]
    assert frame["filename"] == "service.py"
    assert "vars" not in frame
