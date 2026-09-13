"""可替换的 AI Provider 接口与实现。by AI.Coding"""

from app.providers.chat import (
    ChatCompletionResult,
    ChatMessage,
    ChatProvider,
    OpenAICompatibleChatProvider,
)
from app.providers.embedding import EmbeddingProvider, OpenAICompatibleEmbeddingProvider

__all__ = [
    "ChatCompletionResult",
    "ChatMessage",
    "ChatProvider",
    "EmbeddingProvider",
    "OpenAICompatibleChatProvider",
    "OpenAICompatibleEmbeddingProvider",
]
