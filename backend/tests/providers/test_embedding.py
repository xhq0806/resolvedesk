"""Embedding Provider 契约测试。by AI.Coding"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.providers.embedding import (
    OpenAICompatibleEmbeddingProvider,
    VolcengineArkEmbeddingProvider,
)


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


def test_volcengine_ark_embedding_provider_posts_multimodal_text_payload() -> None:
    """方舟 Embedding Provider 应调用多模态接口并传入纯文本内容块。by AI.Coding"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """捕获方舟向量请求并返回 1024 维测试向量。by AI.Coding"""
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": {"embedding": [0.1] * 1024}, "model": "doubao"},
        )

    provider = VolcengineArkEmbeddingProvider(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-secret",
        model="doubao-embedding-vision-251215",
        transport=httpx.MockTransport(handler),
    )
    vectors = asyncio.run(provider.embed(["ResolveDesk FAQ"]))

    body = requests[0].read().decode()
    assert len(vectors) == 1
    assert len(vectors[0]) == 1024
    assert (
        requests[0].url
        == "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
    )
    assert requests[0].headers["authorization"] == "Bearer ark-secret"
    assert '"dimensions":1024' in body
    assert '"type":"text"' in body
