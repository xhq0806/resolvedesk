"""Embedding Provider 契约测试。by AI.Coding"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.providers.embedding import OpenAICompatibleEmbeddingProvider


@pytest.mark.anyio
async def test_embedding_provider_returns_empty_for_empty_input() -> None:
    """空输入不应发起无意义的外部请求。by AI.Coding"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        dimension=2,
        transport=httpx.MockTransport(handler),
    )

    assert await provider.embed([]) == []
    assert requests == []


def test_embedding_provider_posts_compatible_payload() -> None:
    """Provider 应提交模型、批量输入并返回正确向量。by AI.Coding"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}], "model": "demo"},
        )

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        dimension=2,
        transport=httpx.MockTransport(handler),
    )
    vectors = asyncio.run(provider.embed(["hello"]))

    assert vectors == [[0.1, 0.2]]
    assert requests[0].url == "https://provider.example/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer secret"
    assert requests[0].read().decode().find('"model":"demo"') >= 0


def test_embedding_provider_rejects_dimension_mismatch() -> None:
    """Provider 返回错误维度时必须拒绝写入。by AI.Coding"""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        dimension=2,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ValueError, match="维度不匹配"):
        asyncio.run(provider.embed(["hello"]))


def test_embedding_provider_rejects_boolean_values() -> None:
    """向量值不能使用布尔值伪装数字。by AI.Coding"""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [True]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        dimension=1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="非法向量值"):
        asyncio.run(provider.embed(["hello"]))
