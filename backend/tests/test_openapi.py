"""OpenAPI 契约稳定性测试。by AI.Coding"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_ticket_and_user_tags_without_items() -> None:
    """生成的 OpenAPI 应包含 Ticket/User，且不再暴露 Items。by AI.Coding"""
    with TestClient(app) as client:
        openapi = client.get("/api/v1/openapi.json").json()

    paths = openapi["paths"]
    assert "/api/v1/tickets" in paths
    assert "/api/v1/tickets/statistics" in paths
    assert "/api/v1/users/" in paths
    assert all("/items" not in path for path in paths)
    assert paths["/api/v1/tickets"]["get"]["tags"] == ["tickets"]
    assert paths["/api/v1/tickets/statistics"]["get"]["tags"] == ["tickets"]
    assert paths["/api/v1/users/"]["get"]["tags"] == ["users"]
