"""ProviderService 配置加密、校验和连接测试回归。by AI.Coding"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.errors import ConflictError, ErrorCode
from app.core.errors import ValidationError as DomainValidationError
from app.core.secret_crypto import SecretCipher
from app.core.workspace import WorkspaceContext
from app.models.ai import AiProviderConfig
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.ai import ProviderConfigPatch, ProviderTestKind, ProviderTestRequest
from app.services.provider_service import ProviderService


@pytest.fixture
def provider_session() -> Iterator[Session]:
    """创建不依赖 Docker 的内存数据库，仅包含 Provider 测试所需表。by AI.Coding"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 只创建本测试依赖的表，避免一期 User 表的 PostgreSQL 专用默认值影响 SQLite。by AI.Coding
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Workspace.__table__,
            WorkspaceMember.__table__,
            AiProviderConfig.__table__,
        ],
    )
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner_context(provider_session: Session) -> WorkspaceContext:
    """创建具备管理权限的 WorkspaceContext。by AI.Coding"""
    user_id = uuid.uuid4()
    workspace = Workspace(
        name="Provider Workspace",
        slug=f"provider-{uuid.uuid4().hex}",
        owner_user_id=user_id,
    )
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user_id,
        role=WorkspaceRole.OWNER,
    )
    provider_session.add(workspace)
    provider_session.add(member)
    provider_session.commit()
    return WorkspaceContext(workspace=workspace, member=member)


def test_update_config_encrypts_and_hides_api_key(
    provider_session: Session,
    owner_context: WorkspaceContext,
) -> None:
    """更新 Provider 配置时只保存密文并且响应不回显密钥。by AI.Coding"""
    secret = "sk-provider-secret"
    cipher = SecretCipher("provider-test-key")
    result = ProviderService(provider_session, cipher=cipher).update_config(
        owner_context,
        ProviderConfigPatch(
            chat_base_url="https://provider.example/v1/",
            embedding_base_url="https://provider.example/v1/",
            api_key=secret,
        ),
    )

    stored = provider_session.exec(select(AiProviderConfig)).one()

    assert stored.encrypted_api_key is not None
    assert secret.encode() not in stored.encrypted_api_key
    assert cipher.decrypt(stored.encrypted_api_key) == secret
    assert result.has_api_key is True
    assert result.masked_api_key == "********"
    assert secret not in result.model_dump_json()
    assert result.chat_base_url == "https://provider.example/v1"


def test_enabling_incomplete_config_returns_provider_unavailable(
    provider_session: Session,
    owner_context: WorkspaceContext,
) -> None:
    """启用缺字段配置应返回稳定 Provider 不可用错误。by AI.Coding"""
    with pytest.raises(ConflictError) as exc:
        ProviderService(provider_session, cipher=SecretCipher("provider-test-key")).update_config(
            owner_context,
            ProviderConfigPatch(enabled=True),
        )

    assert exc.value.code is ErrorCode.PROVIDER_UNAVAILABLE


def test_update_config_rejects_local_provider_url(
    provider_session: Session,
    owner_context: WorkspaceContext,
) -> None:
    """Provider base URL 不允许配置为 localhost 或内网地址。by AI.Coding"""
    with pytest.raises(DomainValidationError) as exc:
        ProviderService(provider_session, cipher=SecretCipher("provider-test-key")).update_config(
            owner_context,
            ProviderConfigPatch(chat_base_url="http://localhost:11434/v1"),
        )

    assert getattr(exc.value, "code", None) is ErrorCode.VALIDATION_ERROR


def test_chat_connection_failure_does_not_leak_api_key(
    provider_session: Session,
    owner_context: WorkspaceContext,
) -> None:
    """Provider 连接测试失败时只返回稳定错误码，不泄漏 API Key。by AI.Coding"""
    secret = "sk-provider-secret"
    captured_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """模拟 Provider 鉴权失败并记录实际 Authorization 头。by AI.Coding"""
        captured_headers.append(request.headers["authorization"])
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    cipher = SecretCipher("provider-test-key")
    service = ProviderService(provider_session, cipher=cipher)
    service.update_config(
        owner_context,
        ProviderConfigPatch(
            chat_base_url="https://provider.example/v1",
            embedding_base_url="https://provider.example/v1",
            api_key=secret,
        ),
    )

    result = asyncio.run(
        service.test_provider(
            owner_context,
            ProviderTestRequest(kind=ProviderTestKind.CHAT),
            chat_transport=httpx.MockTransport(handler),
        )
    )

    assert captured_headers == [f"Bearer {secret}"]
    assert result.ok is False
    assert result.code == "AUTH_FAILED"
    assert secret not in result.model_dump_json()
