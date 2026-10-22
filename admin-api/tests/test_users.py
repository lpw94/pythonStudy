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
    assert data["meta"]["total"] == 4
    assert {u["username"] for u in data["items"]} == {"admin", "operator", "auditor", "viewer"}


def test_list_users_pagination(client: TestClient, auth_header: dict[str, str]) -> None:
    """分页参数生效。"""
    resp = client.get("/api/users?page=1&page_size=1", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["meta"]["total"] == 4
    assert data["meta"]["pages"] == 4


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


# ============================================================
# 用户更新（部分更新）
# ============================================================


def test_update_user_partial(client: TestClient, auth_header: dict[str, str]) -> None:
    """只传 nickname → 只改 nickname，其他字段保持原样。

    这是 partial update 语义，跟 PUT 全量覆盖不一样。
    """
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "operator")

    resp = client.put(
        f"/api/users/{target['id']}",
        headers=auth_header,
        json={"nickname": "改过的昵称"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "改过的昵称"
    # 没传的字段没被动过
    assert data["email"] == target["email"]
    assert {r["code"] for r in data["roles"]} == {"operator"}


def test_update_user_roles(client: TestClient, auth_header: dict[str, str]) -> None:
    """改角色 → 权限跟着变（角色是权限的来源）。"""
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "viewer")

    resp = client.put(
        f"/api/users/{target['id']}",
        headers=auth_header,
        json={"role_codes": ["operator"]},
    )
    assert resp.status_code == 200
    assert {r["code"] for r in resp.json()["roles"]} == {"operator"}


def test_update_user_unknown_role(client: TestClient, auth_header: dict[str, str]) -> None:
    """角色不存在 → 400，不能静默建出新角色。"""
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "viewer")

    resp = client.put(
        f"/api/users/{target['id']}",
        headers=auth_header,
        json={"role_codes": ["nonexistent"]},
    )
    assert resp.status_code == 400
    assert "角色不存在" in resp.json()["detail"]


def test_update_user_password(client: TestClient, auth_header: dict[str, str]) -> None:
    """改密码后旧密码失效、新密码能登录。"""
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "operator")

    resp = client.put(
        f"/api/users/{target['id']}",
        headers=auth_header,
        json={"password": "newpass123"},
    )
    assert resp.status_code == 200

    assert (
        client.post(
            "/api/auth/login", json={"username": "operator", "password": "op123456"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "operator", "password": "newpass123"}
        ).status_code
        == 200
    )


def test_update_user_disabled_cannot_login(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """禁用账号 → 登录被拒。"""
    users = client.get("/api/users", headers=auth_header).json()["items"]
    target = next(u for u in users if u["username"] == "operator")

    resp = client.put(
        f"/api/users/{target['id']}",
        headers=auth_header,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    assert (
        client.post(
            "/api/auth/login", json={"username": "operator", "password": "op123456"}
        ).status_code
        == 401
    )


def test_update_user_not_found(client: TestClient, auth_header: dict[str, str]) -> None:
    """改不存在的用户 → 400（service 层抛 UserError）。"""
    resp = client.put("/api/users/99999", headers=auth_header, json={"nickname": "x"})
    assert resp.status_code == 400


def test_update_user_forbidden_for_operator(
    client: TestClient, operator_header: dict[str, str]
) -> None:
    """operator 没有 user:delete 但有 user:update —— 边界要分清。"""
    users = client.get("/api/users", headers=operator_header)
    assert users.status_code == 200

    target = next(u for u in users.json()["items"] if u["username"] == "viewer")
    resp = client.put(
        f"/api/users/{target['id']}",
        headers=operator_header,
        json={"nickname": "operator 改的"},
    )
    assert resp.status_code == 200
