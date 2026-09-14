"""Chat Provider 协议单元测试。by AI.Coding"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx

from app.providers.chat import (
    ChatMessage,
    OpenAICompatibleChatProvider,
    VolcengineArkResponsesChatProvider,
)


def test_chat_provider_posts_messages_and_parses_tool_calls() -> None:
    """非流式请求应保留消息、工具调用和结束原因。by AI.Coding"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "lookup_ticket",
                                        "arguments": '{"ticket_id":"TKT-1"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    provider = OpenAICompatibleChatProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        provider.complete(
            [ChatMessage(role="user", content="Find ticket TKT-1")],
            tools=[
                {
                    "type": "function",
                    "function": {"name": "lookup_ticket"},
                }
            ],
        )
    )

    assert result.content is None
    assert result.tool_calls[0]["id"] == "call_1"
    assert result.finish_reason == "tool_calls"
    assert requests[0].url == "https://provider.example/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer secret"
    assert '"stream":false' in requests[0].read().decode()


def test_chat_provider_streams_sse_chunks() -> None:
    """流式接口应跳过非 data 行并在 DONE 后结束。by AI.Coding"""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b": keep-alive\n"
                b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    provider = OpenAICompatibleChatProvider(
        base_url="https://provider.example/v1",
        api_key="secret",
        model="demo",
        transport=httpx.MockTransport(handler),
    )

    async def collect() -> list[dict[str, Any]]:
        """收集测试用流式事件。by AI.Coding"""
        return [event async for event in provider.stream([])]

    events = asyncio.run(collect())
    assert len(events) == 2
    first_delta = cast(dict[str, str], events[0]["choices"][0]["delta"])
    second_delta = cast(dict[str, str], events[1]["choices"][0]["delta"])
    assert first_delta["content"] == "Hel"
    assert second_delta["content"] == "lo"


def test_volcengine_ark_responses_provider_posts_template_payload() -> None:
    """方舟 Responses Provider 应使用截图模板中的 base URL 和 input_text 结构。by AI.Coding"""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """捕获方舟 Responses 请求并返回最小文本响应。by AI.Coding"""
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "你好"}],
                    }
                ],
            },
        )

    provider = VolcengineArkResponsesChatProvider(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-secret",
        model="doubao-seed-2-1-pro-260628",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.complete([ChatMessage(role="user", content="ping")]))

    body = requests[0].read().decode()
    assert result.content == "你好"
    assert requests[0].url == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert requests[0].headers["authorization"] == "Bearer ark-secret"
    assert '"model":"doubao-seed-2-1-pro-260628"' in body
    assert '"type":"input_text"' in body


def test_volcengine_ark_responses_provider_normalizes_stream_deltas() -> None:
    """方舟 Responses SSE 文本增量应转换为项目内部兼容 chunk。by AI.Coding"""

    def handler(_: httpx.Request) -> httpx.Response:
        """模拟方舟 response.output_text.delta 流式事件。by AI.Coding"""
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"type":"response.created"}\n\n'
                b'data: {"type":"response.output_text.delta","delta":"Hel"}\n\n'
                b'data: {"type":"response.output_text.delta","delta":"lo"}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    provider = VolcengineArkResponsesChatProvider(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-secret",
        model="doubao-seed-2-1-pro-260628",
        transport=httpx.MockTransport(handler),
    )

    async def collect() -> list[dict[str, Any]]:
        """收集方舟流式事件的兼容结果。by AI.Coding"""
        return [event async for event in provider.stream([])]

    events = asyncio.run(collect())
    first_delta = cast(dict[str, str], events[0]["choices"][0]["delta"])
    second_delta = cast(dict[str, str], events[1]["choices"][0]["delta"])
    assert first_delta["content"] == "Hel"
    assert second_delta["content"] == "lo"
