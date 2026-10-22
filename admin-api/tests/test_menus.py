"""菜单管理测试。

重点验证：
1. 菜单是**权限的载体**——改菜单的权限码 = 改所有关联角色的权限
2. route_name 全局唯一（前端 addRoute 靠它标识）
3. 删除保护：有子菜单 / 有角色引用时不能删
4. 树结构组装正确（parent_id → children）
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_menus_returns_tree(client: TestClient, auth_header: dict[str, str]) -> None:
    """管理端菜单接口返回树（平铺数据在 service 层组装成树）。"""
    resp = client.get("/api/menus", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert {m["route_name"] for m in data} == {"system-user", "system-role-view", "system-menu"}


def test_list_flat_menus(client: TestClient, auth_header: dict[str, str]) -> None:
    """平铺菜单接口：一维列表，带 parent_id，不组 children。

    「给角色勾菜单」的多选框要用这种形状——一维列表比树好勾。
    """
    resp = client.get("/api/menus/flat", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert {m["route_name"] for m in data} == {"system-user", "system-role-view", "system-menu"}
    # 平铺形状：每个节点都没有 children
    assert all("children" not in m or m["children"] == [] for m in data)


def test_list_permissions(client: TestClient, auth_header: dict[str, str]) -> None:
    """权限码清单从后端来。

    前端菜单编辑页要选权限码，不能把码硬编码在前端——
    后端加了新权限码，前端应该自动能选到。
    """
    resp = client.get("/api/permissions", headers=auth_header)
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert "user:read" in codes
    assert "role:write" in codes
    # 每条都带分组，前端可以按组分栏
    assert all("group" in p for p in resp.json())


def test_create_menu_with_permissions(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """创建菜单并挂权限码。"""
    resp = client.post(
        "/api/menus",
        headers=auth_header,
        json={
            "name": "订单管理",
            "path": "/system/order",
            "component": "system/order",
            "route_name": "system-order",
            "sort": 3,
            "permission_codes": ["user:read"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["route_name"] == "system-order"
    assert data["permissions"] == ["user:read"]


def test_create_menu_duplicate_route_name(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """route_name 重复 → 400。

    路由名必须全局唯一，前端 `addRoute()` 靠它做标识，重复会注册出错。
    """
    resp = client.post(
        "/api/menus",
        headers=auth_header,
        json={
            "name": "重复的用户管理",
            "path": "/system/user2",
            "route_name": "system-user",
        },
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_create_menu_with_unknown_permission(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """权限码不存在 → 400，不能建出一个「有菜单但没权限」的空壳。"""
    resp = client.post(
        "/api/menus",
        headers=auth_header,
        json={
            "name": "坏菜单",
            "path": "/bad",
            "route_name": "bad-menu",
            "permission_codes": ["nonexistent:code"],
        },
    )
    assert resp.status_code == 400
    assert "权限码不存在" in resp.json()["detail"]


def test_create_child_menu(client: TestClient, auth_header: dict[str, str]) -> None:
    """创建子菜单 → 出现在父菜单的 children 里。"""
    menus = client.get("/api/menus", headers=auth_header).json()
    parent = next(m for m in menus if m["route_name"] == "system-user")

    resp = client.post(
        "/api/menus",
        headers=auth_header,
        json={
            "name": "用户详情",
            "path": "/system/user/detail",
            "route_name": "system-user-detail",
            "parent_id": parent["id"],
        },
    )
    assert resp.status_code == 201

    after = client.get("/api/menus", headers=auth_header).json()
    parent_after = next(m for m in after if m["route_name"] == "system-user")
    assert [c["route_name"] for c in parent_after["children"]] == ["system-user-detail"]


def test_update_menu_permissions_changes_role_permissions(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """改菜单的权限码 → 关联角色的权限码跟着变。

    这是「菜单即权限载体」的直接后果：
    菜单上挂的权限码是这个菜单所有关联角色共享的。
    """
    menus = client.get("/api/menus", headers=auth_header).json()
    role_menu = next(m for m in menus if m["route_name"] == "system-role-view")

    # 原本 role_menu 只有 role:read，给它加上 role:write
    resp = client.put(
        f"/api/menus/{role_menu['id']}",
        headers=auth_header,
        json={"permission_codes": ["role:read", "role:write"]},
    )
    assert resp.status_code == 200
    assert set(resp.json()["permissions"]) == {"role:read", "role:write"}

    # auditor 挂了「角色查看」这个菜单 → 权限码跟着变
    roles = {r["code"]: r for r in client.get("/api/roles", headers=auth_header).json()}
    assert "role:write" in roles["auditor"]["permissions"]
    # 没挂这个菜单的 operator 不受影响
    assert "role:write" not in roles["operator"]["permissions"]


def test_update_menu_cannot_parent_itself(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """不能把自己设为自己的父节点（会造出死循环的树）。"""
    menus = client.get("/api/menus", headers=auth_header).json()
    target = next(m for m in menus if m["route_name"] == "system-user")

    resp = client.put(
        f"/api/menus/{target['id']}",
        headers=auth_header,
        json={"parent_id": target["id"]},
    )
    assert resp.status_code == 400
    assert "不能是自己" in resp.json()["detail"]


def test_update_menu_not_found(client: TestClient, auth_header: dict[str, str]) -> None:
    """改不存在的菜单 → 404。"""
    resp = client.put("/api/menus/99999", headers=auth_header, json={"name": "不存在"})
    assert resp.status_code == 404


def test_delete_menu_with_children_rejected(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """有子菜单时不能删父菜单（删了子菜单就成了孤儿）。"""
    menus = client.get("/api/menus", headers=auth_header).json()
    parent = next(m for m in menus if m["route_name"] == "system-user")

    # 先造个子菜单
    child = client.post(
        "/api/menus",
        headers=auth_header,
        json={
            "name": "临时子菜单",
            "path": "/system/user/tmp",
            "route_name": "tmp-child",
            "parent_id": parent["id"],
        },
    ).json()

    resp = client.delete(f"/api/menus/{parent['id']}", headers=auth_header)
    assert resp.status_code == 400
    assert "子菜单" in resp.json()["detail"]

    # 子菜单能删（它没被任何角色引用）
    assert client.delete(f"/api/menus/{child['id']}", headers=auth_header).status_code == 204


def test_delete_menu_used_by_role_rejected(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """还有角色引用时不能删菜单。

    否则那些角色会静默失去这个菜单 → 连带失去它带的权限码。
    """
    menus = client.get("/api/menus", headers=auth_header).json()
    target = next(m for m in menus if m["route_name"] == "system-role-view")

    resp = client.delete(f"/api/menus/{target['id']}", headers=auth_header)
    assert resp.status_code == 400
    assert "角色引用" in resp.json()["detail"]


def test_delete_unused_menu(client: TestClient, auth_header: dict[str, str]) -> None:
    """没被引用的菜单可以删 → 204。"""
    created = client.post(
        "/api/menus",
        headers=auth_header,
        json={"name": "临时菜单", "path": "/tmp", "route_name": "tmp-menu"},
    ).json()

    assert client.delete(f"/api/menus/{created['id']}", headers=auth_header).status_code == 204
    route_names = {m["route_name"] for m in client.get("/api/menus", headers=auth_header).json()}
    assert "tmp-menu" not in route_names


def test_menu_crud_forbidden_for_viewer(client: TestClient, viewer_token: str) -> None:
    """viewer 连菜单都写不了 → 403。"""
    headers = {"Authorization": f"Bearer {viewer_token}"}
    resp = client.post(
        "/api/menus",
        headers=headers,
        json={"name": "越权菜单", "path": "/x", "route_name": "x-menu"},
    )
    assert resp.status_code == 403
    assert "menu:write" in resp.json()["detail"]
