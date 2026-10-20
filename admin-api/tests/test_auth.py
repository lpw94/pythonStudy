"""认证相关测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    """健康检查返回 ok。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_success(client: TestClient) -> None:
    """登录成功返回一对令牌。"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    # access 和 refresh 必须不同，否则 refresh 就没意义了
    assert data["access_token"] != data["refresh_token"]


def test_login_wrong_password(client: TestClient) -> None:
    """密码错误返回 401，且不区分「用户不存在」和「密码错」。"""
    wrong_pwd = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    no_user = client.post(
        "/api/auth/login", json={"username": "not-exist", "password": "whatever"}
    )
    assert wrong_pwd.status_code == 401
    assert no_user.status_code == 401
    # 错误信息完全一致，避免泄露用户名是否存在
    assert wrong_pwd.json()["detail"] == no_user.json()["detail"]


def test_login_validation_error(client: TestClient) -> None:
    """缺字段返回 422（Pydantic 校验拦截，根本不进业务代码）。"""
    resp = client.post("/api/auth/login", json={"username": ""})
    assert resp.status_code == 422


def test_me_requires_token(client: TestClient) -> None:
    """没带 token 返回 401。"""
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_invalid_token(client: TestClient) -> None:
    """token 是乱写的也返回 401。"""
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401


def test_me_returns_profile(client: TestClient, admin_token: str) -> None:
    """带 token 返回用户档案 + 权限 + 菜单。"""
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["roles"] == ["admin"]
    # admin 角色关联了用户管理菜单 → 拿到 user:read 权限码
    assert "user:read" in data["permissions"]
    # 菜单是树形结构
    route_names = [m["route_name"] for m in data["menus"]]
    assert "system-user" in route_names


def test_refresh_token_exchange(client: TestClient) -> None:
    """用 refresh token 能换到新的 access token。"""
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    ).json()
    resp = client.post(
        "/api/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_access_token_cannot_be_used_as_refresh(client: TestClient, admin_token: str) -> None:
    """access token 不能当 refresh token 用（type 校验生效）。"""
    resp = client.post("/api/auth/refresh", json={"refresh_token": admin_token})
    assert resp.status_code == 401
