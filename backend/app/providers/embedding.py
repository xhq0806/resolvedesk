"""OpenAI-compatible Embedding Provider。by AI.Coding"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    """Embedding Provider 的最小业务接口。by AI.Coding"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量。by AI.Coding"""
        ...


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingProvider:
    """调用 OpenAI-compatible /embeddings 接口并校验向量维度。by AI.Coding"""

    base_url: str
    api_key: str
    model: str
    dimension: int = 1536
    timeout_seconds: float = 30.0
    transport: httpx.AsyncBaseTransport | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """提交批量文本并返回经过维度校验的向量列表。by AI.Coding"""
        if not texts:
            return []
        payload = {"model": self.model, "input": texts, "encoding_format": "float"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        endpoint = f"{self.base_url.rstrip('/')}/embeddings"
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        vectors = body.get("data") if isinstance(body, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ValueError("Embedding provider 返回数量与输入不一致。")
        result: list[list[float]] = []
        for item in vectors:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or len(vector) != self.dimension:
                raise ValueError("Embedding provider 返回向量维度不匹配。")
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and isfinite(float(value))
                for value in vector
            ):
                raise ValueError("Embedding provider 返回了非法向量值。")
            result.append([float(value) for value in vector])
        return result


@dataclass(frozen=True)
class VolcengineArkEmbeddingProvider:
    """调用火山方舟多模态向量化接口处理纯文本 RAG 切块。by AI.Coding"""

    base_url: str
    api_key: str
    model: str
    dimension: int = 1024
    timeout_seconds: float = 30.0
    transport: httpx.AsyncBaseTransport | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """逐条提交文本并返回方舟指定维度的向量。by AI.Coding"""
        if not texts:
            return []
        result: list[list[float]] = []
        for text in texts:
            result.append(await self._embed_one(text))
        return result

    async def _embed_one(self, text: str) -> list[float]:
        """调用 /embeddings/multimodal 并校验单条文本向量。by AI.Coding"""
        payload = {
            "model": self.model,
            "encoding_format": "float",
            "dimensions": self.dimension,
            "input": [{"type": "text", "text": text}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        endpoint = f"{self.base_url.rstrip('/')}/embeddings/multimodal"
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        vector = data.get("embedding") if isinstance(data, dict) else None
        return self._validate_vector(vector)

    def _validate_vector(self, vector: object) -> list[float]:
        """校验火山方舟返回向量的维度和数值类型。by AI.Coding"""
        if not isinstance(vector, list) or len(vector) != self.dimension:
            raise ValueError("Embedding provider 返回向量维度不匹配。")
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(float(value))
            for value in vector
        ):
            raise ValueError("Embedding provider 返回了非法向量值。")
        return [float(value) for value in vector]
