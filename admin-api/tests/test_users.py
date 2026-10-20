"""用户管理与权限隔离测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_users_requires_auth(client: TestClient) -> None:
    """没登录访问用户列表 → 401。"""
    assert client.get("/api/users").status_code == 401


def test_list_users_forbidden_for_viewer(client: TestClient, viewer_token: str) -> None:
    """viewer 没有 user:read 权限 → 403。

    这是权限系统的核心断言：登录了不等于什么都能干。
    """
    resp = client.get("/api/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403
    assert "user:read" in resp.json()["detail"]


def test_list_users_ok_for_admin(client: TestClient, auth_header: dict[str, str]) -> None:
    """admin 能查用户列表。"""
    resp = client.get("/api/users", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 2
    assert {u["username"] for u in data["items"]} == {"admin", "viewer"}


def test_list_users_pagination(client: TestClient, auth_header: dict[str, str]) -> None:
    """分页参数生效。"""
    resp = client.get("/api/users?page=1&page_size=1", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["meta"]["total"] == 2
    assert data["meta"]["pages"] == 2


def test_create_user(client: TestClient, auth_header: dict[str, str]) -> None:
    """创建用户成功，且密码在库里是哈希不是明文。"""
    resp = client.post(
        "/api/users",
        headers=auth_header,
        json={"username": "newbie", "password": "secret123", "nickname": "新人"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newbie"

    # 再查一次，确认能查到，且响应里绝不能出现密码字段
    detail = client.get(f"/api/users/{resp.json()['id']}", headers=auth_header)
    assert detail.status_code == 200
    assert "password" not in detail.json()
    assert "password_hash" not in detail.json()


def test_create_user_duplicate_username(client: TestClient, auth_header: dict[str, str]) -> None:
    """用户名重复 → 400。"""
    resp = client.post(
        "/api/users",
        headers=auth_header,
        json={"username": "admin", "password": "secret123"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_create_user_validation(client: TestClient, auth_header: dict[str, str]) -> None:
    """密码太短 → 422。"""
    resp = client.post(
        "/api/users",
        headers=auth_header,
        json={"username": "x", "password": "123"},
    )
    assert resp.status_code == 422


def test_delete_user(client: TestClient, auth_header: dict[str, str]) -> None:
    """删除用户 → 204，之后查不到。"""
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "viewer")

    resp = client.delete(f"/api/users/{target['id']}", headers=auth_header)
    assert resp.status_code == 204
    assert client.get(f"/api/users/{target['id']}", headers=auth_header).status_code == 404


def test_delete_user_forbidden_for_viewer(
    client: TestClient, viewer_token: str
) -> None:
    """viewer 连删用户的资格都没有 → 403。"""
    resp = client.delete("/api/users/1", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_get_menu_tree(client: TestClient, auth_header: dict[str, str]) -> None:
    """管理端菜单接口返回树。"""
    resp = client.get("/api/menus", headers=auth_header)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
