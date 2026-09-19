"""知识检索策略与追踪 API 测试。by AI.Coding"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models.knowledge import RagRetrievalTrace
from app.models.workspace import Workspace


def _workspace_id(headers: dict[str, str]) -> str:
    """从测试请求头读取已授权的 Workspace ID。by AI.Coding"""
    return headers["X-Workspace-ID"]


def test_retrieval_policy_requires_manager(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Customer 不得读取或更改 Workspace 的检索策略。by AI.Coding"""
    workspace_id = _workspace_id(normal_user_token_headers)

    response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/knowledge/retrieval-policy",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


def test_manager_can_enable_trace_and_list_only_own_workspace_records(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """管理者应能启停本租户 trace，列表不得混入其他 Workspace。by AI.Coding"""
    workspace_id = _workspace_id(superuser_token_headers)
    update_response = client.patch(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/knowledge/retrieval-policy",
        headers=superuser_token_headers,
        json={"trace_enabled": True, "strategy_version": "dense-v1"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["trace_enabled"] is True

    workspace = db.exec(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id))).one()
    db.add(
        RagRetrievalTrace(
            workspace_id=workspace.id,
            request_id="own-request",
            query_fingerprint="a" * 64,
            query_length=4,
            strategy_version="dense-v1",
            result_count=1,
            elapsed_ms=5,
            candidates=[],
        )
    )
    # 为另一个 Workspace 写入 trace，验证列表查询始终绑定当前租户。by AI.Coding
    other_workspace = Workspace(
        name="Other Trace Workspace",
        slug=f"other-trace-{uuid.uuid4().hex[:8]}",
        owner_user_id=workspace.owner_user_id,
    )
    db.add(other_workspace)
    db.flush()
    db.add(
        RagRetrievalTrace(
            workspace_id=other_workspace.id,
            request_id="other-request",
            query_fingerprint="b" * 64,
            query_length=3,
            strategy_version="dense-v1",
            result_count=1,
            elapsed_ms=5,
            candidates=[],
        )
    )
    db.commit()

    list_response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/knowledge/retrieval-traces",
        headers=superuser_token_headers,
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["request_id"] == "own-request"
    assert "query" not in payload[0]
