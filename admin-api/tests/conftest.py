"""pytest fixtures：测试用的数据库和客户端。

对标前端：jest setup + beforeEach 的全局准备。
关键点：**每个测试用独立的内存数据库**，互不干扰。
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from admin_api.core.security import hash_password
from admin_api.database import Base, get_db
from admin_api.main import app
from admin_api.models import Menu, Permission, Role, User

# 内存 SQLite：StaticPool 让所有连接共用同一个内存库，
# 否则每个新连接都会得到一个全新的空数据库。
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db() -> Generator[Session, None, None]:
    """替换掉生产用的 get_db 依赖，指向测试库。"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """每个测试一个干净库：建表 → 灌数据 → 测试 → 删表。"""
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestingSessionLocal()
    _seed(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


def _seed(db: Session) -> None:
    """灌最小测试数据：一个 admin、一个 viewer、两个菜单、两个权限。"""
    perms = {
        "user:read": Permission(code="user:read", name="查看用户", group="用户管理"),
        "user:delete": Permission(code="user:delete", name="删除用户", group="用户管理"),
    }
    for p in perms.values():
        db.add(p)

    user_menu = Menu(
        name="用户管理",
        path="/system/user",
        component="system/user",
        route_name="system-user",
        sort=1,
        parent_id=0,
        permissions=[perms["user:read"]],
    )
    db.add(user_menu)
    db.flush()

    admin_role = Role(code="admin", name="管理员", remark="")
    admin_role.menus = [user_menu]
    viewer_role = Role(code="viewer", name="只读", remark="")

    db.add_all(
        [
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                nickname="管理员",
                roles=[admin_role],
            ),
            User(
                username="viewer",
                password_hash=hash_password("view123"),
                nickname="只读用户",
                roles=[viewer_role],
            ),
        ]
    )
    db.commit()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI 测试客户端。

    TestClient 用 httpx 模拟真实 HTTP 请求（不经过网络栈），
    对标前端的 supertest / msw。
    """
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(client: TestClient) -> str:
    """已登录 admin 的 access token。"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def viewer_token(client: TestClient) -> str:
    """已登录 viewer 的 access token。"""
    resp = client.post("/api/auth/login", json={"username": "viewer", "password": "view123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_header(admin_token: str) -> dict[str, str]:
    """带 Authorization 头的请求参数。"""
    return {"Authorization": f"Bearer {admin_token}"}
