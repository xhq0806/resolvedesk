"""AI Provider 配置、加密和连接测试服务。by AI.Coding"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    ValidationError,
)
from app.core.provider_security import validate_provider_base_url
from app.core.secret_crypto import SecretCipher, secret_cipher_from_settings
from app.core.workspace import WorkspaceContext, WorkspacePolicy
from app.models.ai import AiProviderConfig
from app.models.user import get_datetime_utc
from app.providers.chat import (
    ChatMessage,
    OpenAICompatibleChatProvider,
    VolcengineArkResponsesChatProvider,
)
from app.providers.embedding import (
    OpenAICompatibleEmbeddingProvider,
    VolcengineArkEmbeddingProvider,
)
from app.schemas.ai import (
    ProviderConfigPatch,
    ProviderConfigPublic,
    ProviderTestKind,
    ProviderTestRequest,
    ProviderTestResult,
)

ResultType = TypeVar("ResultType")

VOLCENGINE_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
VOLCENGINE_ARK_CHAT_MODEL = "doubao-seed-2-1-pro-260628"
VOLCENGINE_ARK_EMBEDDING_MODEL = "doubao-embedding-vision-251215"
SUPPORTED_EMBEDDING_DIMENSION = 1024


class ProviderService:
    """管理 Workspace 级模型 Provider 配置和可用性检测。by AI.Coding"""

    def __init__(
        self,
        session: Session,
        *,
        cipher: SecretCipher | None = None,
    ) -> None:
        """保存请求级 session 和密钥加密器。by AI.Coding"""
        self.session = session
        self.cipher = cipher or secret_cipher_from_settings()

    def get_config(self, context: WorkspaceContext) -> ProviderConfigPublic:
        """返回当前 Workspace 的脱敏 Provider 配置。by AI.Coding"""
        WorkspacePolicy.require_manager(context)
        config = self._get_or_create_config(context)
        self.session.commit()
        self.session.refresh(config)
        return self._public(config)

    def update_config(
        self, context: WorkspaceContext, payload: ProviderConfigPatch
    ) -> ProviderConfigPublic:
        """写入 Provider 配置并保证 API Key 不回显。by AI.Coding"""
        WorkspacePolicy.require_manager(context)

        def operation() -> AiProviderConfig:
            config = self._get_or_create_config(context)
            if payload.chat_provider is not None:
                config.chat_provider = payload.chat_provider
            if payload.chat_base_url is not None:
                config.chat_base_url = self._validated_url(payload.chat_base_url)
            if payload.chat_model is not None:
                config.chat_model = payload.chat_model
            if payload.embedding_provider is not None:
                config.embedding_provider = payload.embedding_provider
            if payload.embedding_base_url is not None:
                config.embedding_base_url = self._validated_url(
                    payload.embedding_base_url
                )
            if payload.embedding_model is not None:
                config.embedding_model = payload.embedding_model
            if payload.embedding_dimension is not None:
                config.embedding_dimension = payload.embedding_dimension
            if payload.clear_api_key:
                config.encrypted_api_key = None
            if payload.api_key is not None:
                config.encrypted_api_key = self.cipher.encrypt(payload.api_key)
            if payload.enabled is not None:
                config.enabled = payload.enabled
            if config.enabled:
                self._ensure_ready(config)
            config.updated_at = get_datetime_utc()
            self.session.add(config)
            return config

        config = self._write(operation)
        return self._public(config)

    async def test_provider(
        self,
        context: WorkspaceContext,
        payload: ProviderTestRequest,
        *,
        chat_transport: httpx.AsyncBaseTransport | None = None,
        embedding_transport: httpx.AsyncBaseTransport | None = None,
    ) -> ProviderTestResult:
        """在数据库事务外执行 Provider 连接测试。by AI.Coding"""
        WorkspacePolicy.require_manager(context)
        config = self._get_or_create_config(context)
        self.session.commit()
        start = time.perf_counter()
        if config.encrypted_api_key is None:
            return self._failed(payload.kind, "PROVIDER_UNAVAILABLE", start)
        try:
            api_key = self.cipher.decrypt(config.encrypted_api_key)
            if payload.kind is ProviderTestKind.CHAT:
                await self._test_chat(config, api_key, transport=chat_transport)
            else:
                await self._test_embedding(
                    config, api_key, transport=embedding_transport
                )
        except httpx.TimeoutException:
            return self._failed(payload.kind, "TIMEOUT", start)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                return self._failed(payload.kind, "AUTH_FAILED", start)
            return self._failed(payload.kind, "HTTP_ERROR", start)
        except httpx.HTTPError:
            return self._failed(payload.kind, "NETWORK_ERROR", start)
        except ValueError:
            return self._failed(payload.kind, "INVALID_RESPONSE", start)
        return ProviderTestResult(
            kind=payload.kind,
            ok=True,
            message="Provider 连接测试通过。",
            latency_ms=self._latency_ms(start),
        )

    def build_chat_provider(
        self, context: WorkspaceContext
    ) -> OpenAICompatibleChatProvider | VolcengineArkResponsesChatProvider:
        """从已启用配置创建 Chat Provider。by AI.Coding"""
        config = self._get_or_create_config(context)
        self._ensure_ready(config)
        if config.chat_base_url is None or config.encrypted_api_key is None:
            raise ConflictError(ErrorCode.PROVIDER_UNAVAILABLE)
        if config.chat_provider == "volcengine-ark-responses":
            return VolcengineArkResponsesChatProvider(
                base_url=config.chat_base_url,
                api_key=self.cipher.decrypt(config.encrypted_api_key),
                model=config.chat_model,
            )
        return OpenAICompatibleChatProvider(
            base_url=config.chat_base_url,
            api_key=self.cipher.decrypt(config.encrypted_api_key),
            model=config.chat_model,
        )

    def build_embedding_provider(
        self, context: WorkspaceContext
    ) -> OpenAICompatibleEmbeddingProvider | VolcengineArkEmbeddingProvider:
        """从已启用配置创建 Embedding Provider。by AI.Coding"""
        config = self._get_or_create_config(context)
        self._ensure_ready(config)
        if config.embedding_base_url is None or config.encrypted_api_key is None:
            raise ConflictError(ErrorCode.PROVIDER_UNAVAILABLE)
        if config.embedding_provider == "volcengine-ark":
            return VolcengineArkEmbeddingProvider(
                base_url=config.embedding_base_url,
                api_key=self.cipher.decrypt(config.encrypted_api_key),
                model=config.embedding_model,
                dimension=config.embedding_dimension,
            )
        return OpenAICompatibleEmbeddingProvider(
            base_url=config.embedding_base_url,
            api_key=self.cipher.decrypt(config.encrypted_api_key),
            model=config.embedding_model,
            dimension=config.embedding_dimension,
        )

    def _get_or_create_config(self, context: WorkspaceContext) -> AiProviderConfig:
        """读取或创建当前 Workspace 的 Provider 配置。by AI.Coding"""
        config = self.session.exec(
            select(AiProviderConfig).where(
                AiProviderConfig.workspace_id == context.workspace_id
            )
        ).first()
        if config is not None:
            return config
        config = AiProviderConfig(workspace_id=context.workspace_id)
        self.session.add(config)
        self.session.flush()
        return config

    def _write(self, operation: Callable[[], ResultType]) -> ResultType:
        """执行单次 Provider 配置写事务并统一回滚。by AI.Coding"""
        try:
            result = operation()
            self.session.flush()
            self.session.commit()
            # operation 目前固定返回 ORM 配置对象，显式刷新避免泛型 refresh 误用。by AI.Coding
            if isinstance(result, AiProviderConfig):
                self.session.refresh(result)
            return result
        except AppError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(ErrorCode.WORKSPACE_MEMBER_CONFLICT) from exc
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _validated_url(raw_url: str) -> str:
        """把 URL 安全校验错误翻译为稳定领域错误。by AI.Coding"""
        try:
            return validate_provider_base_url(raw_url)
        except ValueError as exc:
            raise ValidationError(ErrorCode.VALIDATION_ERROR) from exc

    @staticmethod
    def _ensure_ready(config: AiProviderConfig) -> None:
        """启用或调用前确认配置具备最小可用字段。by AI.Coding"""
        if (
            not config.enabled
            or not config.chat_base_url
            or not config.embedding_base_url
            or not config.chat_model
            or not config.embedding_model
            or config.embedding_dimension != SUPPORTED_EMBEDDING_DIMENSION
            or config.encrypted_api_key is None
        ):
            raise ConflictError(ErrorCode.PROVIDER_UNAVAILABLE)

    @staticmethod
    def _public(config: AiProviderConfig) -> ProviderConfigPublic:
        """构造不包含 API Key 原文的公开配置。by AI.Coding"""
        has_api_key = config.encrypted_api_key is not None
        return ProviderConfigPublic(
            id=config.id,
            workspace_id=config.workspace_id,
            chat_provider=config.chat_provider,
            chat_base_url=config.chat_base_url,
            chat_model=config.chat_model,
            embedding_provider=config.embedding_provider,
            embedding_base_url=config.embedding_base_url,
            embedding_model=config.embedding_model,
            embedding_dimension=config.embedding_dimension,
            has_api_key=has_api_key,
            masked_api_key="********" if has_api_key else None,
            enabled=config.enabled,
            updated_at=config.updated_at,
        )

    async def _test_chat(
        self,
        config: AiProviderConfig,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        """向 Chat Provider 发起最小健康检查请求。by AI.Coding"""
        if not config.chat_base_url:
            raise ValueError("Chat base URL 未配置。")
        if config.chat_provider == "volcengine-ark-responses":
            ark_provider = VolcengineArkResponsesChatProvider(
                base_url=config.chat_base_url,
                api_key=api_key,
                model=config.chat_model,
                timeout_seconds=15.0,
                transport=transport,
            )
            await ark_provider.complete([ChatMessage(role="user", content="ping")])
            return
        compatible_provider = OpenAICompatibleChatProvider(
            base_url=config.chat_base_url,
            api_key=api_key,
            model=config.chat_model,
            timeout_seconds=15.0,
            transport=transport,
        )
        await compatible_provider.complete([ChatMessage(role="user", content="ping")])

    async def _test_embedding(
        self,
        config: AiProviderConfig,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        """向 Embedding Provider 发起最小健康检查请求。by AI.Coding"""
        if not config.embedding_base_url:
            raise ValueError("Embedding base URL 未配置。")
        if config.embedding_provider == "volcengine-ark":
            ark_provider = VolcengineArkEmbeddingProvider(
                base_url=config.embedding_base_url,
                api_key=api_key,
                model=config.embedding_model,
                dimension=config.embedding_dimension,
                timeout_seconds=15.0,
                transport=transport,
            )
            await ark_provider.embed(["ResolveDesk provider test"])
            return
        compatible_provider = OpenAICompatibleEmbeddingProvider(
            base_url=config.embedding_base_url,
            api_key=api_key,
            model=config.embedding_model,
            dimension=config.embedding_dimension,
            timeout_seconds=15.0,
            transport=transport,
        )
        await compatible_provider.embed(["ResolveDesk provider test"])

    def _failed(
        self,
        kind: ProviderTestKind,
        code: str,
        start: float,
    ) -> ProviderTestResult:
        """返回不包含异常原文和密钥的失败结果。by AI.Coding"""
        return ProviderTestResult(
            kind=kind,
            ok=False,
            code=code,
            message=self._failure_message(code),
            latency_ms=self._latency_ms(start),
        )

    @staticmethod
    def _failure_message(code: str) -> str:
        """把内部失败码转换为稳定中文提示。by AI.Coding"""
        messages = {
            "PROVIDER_UNAVAILABLE": "Provider 配置不完整。",
            "TIMEOUT": "Provider 请求超时。",
            "AUTH_FAILED": "Provider 鉴权失败。",
            "HTTP_ERROR": "Provider 返回错误状态。",
            "NETWORK_ERROR": "无法连接 Provider。",
            "INVALID_RESPONSE": "Provider 返回格式无效。",
        }
        return messages.get(code, "Provider 连接测试失败。")

    @staticmethod
    def _latency_ms(start: float) -> int:
        """计算连接测试耗时毫秒数。by AI.Coding"""
        return int((time.perf_counter() - start) * 1000)
