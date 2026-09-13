"""Chat Provider 协议单元测试。by AI.Coding"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx

from app.providers.chat import ChatMessage, OpenAICompatibleChatProvider


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
