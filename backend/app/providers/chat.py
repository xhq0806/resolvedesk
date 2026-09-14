"""OpenAI-compatible Chat Provider 适配器。by AI.Coding"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ChatMessage:
    """模型上下文中的单条消息。by AI.Coding"""

    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """转换为 OpenAI-compatible 请求消息。by AI.Coding"""
        payload: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            payload["content"] = self.content
        if self.name is not None:
            payload["name"] = self.name
        if self.tool_calls is not None:
            payload["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            payload["tool_call_id"] = self.tool_call_id
        return payload


@dataclass(frozen=True)
class ChatCompletionResult:
    """非流式 Chat completion 的最小稳定结果。by AI.Coding"""

    content: str | None
    tool_calls: list[dict[str, Any]]
    finish_reason: str | None
    raw: dict[str, Any]


class ChatProvider(Protocol):
    """Agent 编排依赖的最小 Chat Provider 接口。by AI.Coding"""

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> ChatCompletionResult:
        """执行一次非流式对话请求。by AI.Coding"""
        ...

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """按 provider chunk 逐条返回流式事件。by AI.Coding"""
        ...


@dataclass(frozen=True)
class OpenAICompatibleChatProvider:
    """调用 OpenAI-compatible /chat/completions 接口。by AI.Coding"""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    transport: httpx.AsyncBaseTransport | None = None

    def _payload(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        stream: bool,
    ) -> dict[str, Any]:
        """构建请求体并显式控制可选能力。by AI.Coding"""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_payload() for message in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def _client(self) -> httpx.AsyncClient:
        """创建带超时和测试 transport 的 HTTP 客户端。by AI.Coding"""
        return httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport)

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> ChatCompletionResult:
        """发送非流式请求并校验最小响应结构。by AI.Coding"""
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self._client() as client:
            response = await client.post(
                endpoint,
                json=self._payload(
                    messages, tools=tools, temperature=temperature, stream=False
                ),
                headers=headers,
            )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Chat provider 返回格式无效。")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Chat provider 未返回 choices。")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            raise ValueError("Chat provider 未返回 message。")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("Chat provider 返回了无效 content。")
        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise ValueError("Chat provider 返回了无效 tool_calls。")
        finish_reason = first.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise ValueError("Chat provider 返回了无效 finish_reason。")
        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw=body,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """解析 SSE data 行并按 chunk 返回 provider 事件。by AI.Coding"""
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self._client() as client:
            async with client.stream(
                "POST",
                endpoint,
                json=self._payload(
                    messages, tools=tools, temperature=temperature, stream=True
                ),
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ValueError("Chat provider 返回了无效 SSE 数据。") from exc
                    if not isinstance(event, dict):
                        raise ValueError("Chat provider SSE 事件格式无效。")
                    yield event


@dataclass(frozen=True)
class VolcengineArkResponsesChatProvider:
    """调用火山方舟 OpenAI SDK 兼容的 Responses API。by AI.Coding"""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    transport: httpx.AsyncBaseTransport | None = None

    def _input(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        """把内部 ChatMessage 转为方舟 Responses API 的 input 消息。by AI.Coding"""
        result: list[dict[str, Any]] = []
        for message in messages:
            if message.content is None:
                continue
            # 方舟模板采用 input_text 内容块；这里只传文本，避免把未授权多模态 URL 写进模型请求。by AI.Coding
            result.append(
                {
                    "type": "message",
                    "role": message.role,
                    "content": [{"type": "input_text", "text": message.content}],
                }
            )
        return result

    def _payload(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None,
        stream: bool,
    ) -> dict[str, Any]:
        """构造火山方舟 Responses 请求体。by AI.Coding"""
        payload: dict[str, Any] = {
            "model": self.model,
            "input": self._input(messages),
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def _client(self) -> httpx.AsyncClient:
        """创建带超时和测试 transport 的 HTTP 客户端。by AI.Coding"""
        return httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport)

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> ChatCompletionResult:
        """发送非流式 Responses 请求并提取 assistant 文本。by AI.Coding"""
        del tools
        endpoint = f"{self.base_url.rstrip('/')}/responses"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self._client() as client:
            response = await client.post(
                endpoint,
                json=self._payload(messages, temperature=temperature, stream=False),
                headers=headers,
            )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("火山方舟返回格式无效。")
        return ChatCompletionResult(
            content=self._extract_response_text(body),
            tool_calls=[],
            finish_reason=self._finish_reason(body),
            raw=body,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """解析 Responses SSE 并转换为项目内部兼容的 delta chunk。by AI.Coding"""
        del tools
        endpoint = f"{self.base_url.rstrip('/')}/responses"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with self._client() as client:
            async with client.stream(
                "POST",
                endpoint,
                json=self._payload(messages, temperature=temperature, stream=True),
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ValueError("火山方舟返回了无效 SSE 数据。") from exc
                    if not isinstance(event, dict):
                        raise ValueError("火山方舟 SSE 事件格式无效。")
                    delta = event.get("delta")
                    if event.get("type") == "response.output_text.delta" and isinstance(
                        delta, str
                    ):
                        yield {"choices": [{"delta": {"content": delta}}]}

    @staticmethod
    def _extract_response_text(body: dict[str, Any]) -> str:
        """从 Responses 完整响应中提取文本内容。by AI.Coding"""
        output = body.get("output")
        if not isinstance(output, list):
            raise ValueError("火山方舟未返回 output。")
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        if not parts:
            raise ValueError("火山方舟未返回文本内容。")
        return "".join(parts)

    @staticmethod
    def _finish_reason(body: dict[str, Any]) -> str | None:
        """把 Responses 状态映射为项目使用的结束原因。by AI.Coding"""
        status = body.get("status")
        return status if isinstance(status, str) else None
