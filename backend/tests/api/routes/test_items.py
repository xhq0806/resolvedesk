"""验证模板 Items API 已随数据表一起退出。by AI.Coding"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_items_route_is_retired() -> None:
    """旧 Items 路径应返回 404，避免访问已删除的数据表。by AI.Coding"""
    with TestClient(app) as client:
        response = client.get(f"{settings.API_V1_STR}/items/")

    assert response.status_code == 404


def test_items_are_absent_from_openapi() -> None:
    """OpenAPI 契约不得继续发布已退出的 Items 接口。by AI.Coding"""
    with TestClient(app) as client:
        paths = client.get(f"{settings.API_V1_STR}/openapi.json").json()["paths"]

    assert all("/items" not in path for path in paths)
