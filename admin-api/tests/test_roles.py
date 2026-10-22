"""角色管理测试。

重点验证三件事：
1. **权限推导**：角色的权限码不是直接存的，是「菜单 → 权限」推导出来的
2. **删除保护**：角色下还有用户时不能删（否则用户静默失去权限）
3. **权限边界**：operator 能读角色但不能写，viewer 什么都干不了
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_roles_requires_auth(client: TestClient) -> None:
    """没登录 → 401。"""
    assert client.get("/api/roles").status_code == 401


def test_list_roles_forbidden_for_viewer(client: TestClient, viewer_token: str) -> None:
    """viewer 没有 role:read → 403。"""
    resp = client.get("/api/roles", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403
    assert "role:read" in resp.json()["detail"]


def test_list_roles_ok_for_admin(client: TestClient, auth_header: dict[str, str]) -> None:
    """admin 能查角色列表。"""
    resp = client.get("/api/roles", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert {r["code"] for r in data} == {"admin", "operator", "auditor", "viewer"}


def test_role_permissions_derived_from_menus(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """角色的权限码由「关联菜单的权限」推导出来。

    这条断言是整个权限模型的骨架：
    角色 → 菜单 → 权限码，用户身上不直接挂权限。
    """
    resp = client.get("/api/roles", headers=auth_header)
    roles = {r["code"]: r for r in resp.json()}

    # admin 挂了全部菜单 → 所有权限码
    assert set(roles["admin"]["permissions"]) == {
        "user:read",
        "user:create",
        "user:update",
        "menu:read",
        "menu:write",
        "role:read",
    }
    # auditor 只挂「角色查看」菜单 → 只有 role:read
    assert roles["auditor"]["permissions"] == ["role:read"]
    # operator 挂用户管理 + 菜单管理 → 有 user:* menu:*，没有 role:*
    assert "user:read" in roles["operator"]["permissions"]
    assert "menu:write" in roles["operator"]["permissions"]
    assert "role:read" not in roles["operator"]["permissions"]
    # viewer 没挂菜单 → 零权限
    assert roles["viewer"]["permissions"] == []
    assert roles["viewer"]["menu_ids"] == []


def test_role_user_count(client: TestClient, auth_header: dict[str, str]) -> None:
    """角色列表带用户数——前端要显示「这个角色下有几个人」。"""
    resp = client.get("/api/roles", headers=auth_header)
    roles = {r["code"]: r for r in resp.json()}
    assert roles["admin"]["user_count"] == 1
    assert roles["viewer"]["user_count"] == 1
    assert roles["operator"]["user_count"] == 1


def test_create_role(client: TestClient, auth_header: dict[str, str]) -> None:
    """创建角色并关联菜单 → 权限码随之推导出来。"""
    menus = client.get("/api/menus", headers=auth_header).json()
    user_menu = next(m for m in menus if m["route_name"] == "system-user")

    resp = client.post(
        "/api/roles",
        headers=auth_header,
        json={
            "code": "newrole",
            "name": "新角色",
            "remark": "只读审计",
            "menu_ids": [user_menu["id"]],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "newrole"
    assert "user:read" in data["permissions"]
    assert "role:read" not in data["permissions"]


def test_create_role_duplicate_code(client: TestClient, auth_header: dict[str, str]) -> None:
    """角色 code 重复 → 400。"""
    resp = client.post(
        "/api/roles",
        headers=auth_header,
        json={"code": "admin", "name": "重复的管理员"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_create_role_invalid_code(client: TestClient, auth_header: dict[str, str]) -> None:
    """code 格式非法（数字开头）→ 422，压根进不了业务代码。"""
    resp = client.post(
        "/api/roles",
        headers=auth_header,
        json={"code": "1admin", "name": "非法"},
    )
    assert resp.status_code == 422


def test_create_role_with_unknown_menu(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """关联不存在的菜单 → 400，不能静默建出一个空角色。"""
    resp = client.post(
        "/api/roles",
        headers=auth_header,
        json={"code": "ghost", "name": "幽灵", "menu_ids": [99999]},
    )
    assert resp.status_code == 400
    assert "菜单不存在" in resp.json()["detail"]


def test_update_role_menus_changes_permissions(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """改角色关联的菜单 → 权限码跟着变。

    这就是「授权」的实际动作：不是给角色挂权限码，是勾菜单。
    """
    roles = client.get("/api/roles", headers=auth_header).json()
    viewer = next(r for r in roles if r["code"] == "viewer")
    menus = client.get("/api/menus", headers=auth_header).json()
    user_menu = next(m for m in menus if m["route_name"] == "system-user")

    resp = client.put(
        f"/api/roles/{viewer['id']}",
        headers=auth_header,
        json={"name": "只读（升级）", "menu_ids": [user_menu["id"]]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "只读（升级）"
    assert "user:read" in data["permissions"]


def test_update_role_not_found(client: TestClient, auth_header: dict[str, str]) -> None:
    """改不存在的角色 → 404。"""
    resp = client.put(
        "/api/roles/99999",
        headers=auth_header,
        json={"name": "不存在"},
    )
    assert resp.status_code == 404


def test_delete_role_with_users_rejected(
    client: TestClient, auth_header: dict[str, str]
) -> None:
    """角色下还有用户 → 拒绝删除。

    这是最关键的一条保护：直接删掉会让那些用户静默失去所有权限，
    排查起来极其痛苦。
    """
    roles = client.get("/api/roles", headers=auth_header).json()
    admin_role = next(r for r in roles if r["code"] == "admin")

    resp = client.delete(f"/api/roles/{admin_role['id']}", headers=auth_header)
    assert resp.status_code == 400
    assert "还有用户" in resp.json()["detail"]


def test_delete_empty_role(client: TestClient, auth_header: dict[str, str]) -> None:
    """没用户的角色可以删 → 204。"""
    resp = client.post(
        "/api/roles",
        headers=auth_header,
        json={"code": "temp", "name": "临时角色"},
    )
    role_id = resp.json()["id"]

    assert client.delete(f"/api/roles/{role_id}", headers=auth_header).status_code == 204
    codes = {r["code"] for r in client.get("/api/roles", headers=auth_header).json()}
    assert "temp" not in codes


def test_auditor_can_read_roles_but_not_write(
    client: TestClient, auditor_header: dict[str, str]
) -> None:
    """auditor 有 role:read 但没有 role:write → 读得了、写不了。

    权限码是「按菜单授予」的：auditor 挂的「角色查看」菜单只声明了 role:read。
    """
    assert client.get("/api/roles", headers=auditor_header).status_code == 200

    resp = client.post(
        "/api/roles",
        headers=auditor_header,
        json={"code": "nope", "name": "不该建成"},
    )
    assert resp.status_code == 403
    assert "role:write" in resp.json()["detail"]


def test_operator_cannot_read_roles(client: TestClient, operator_header: dict[str, str]) -> None:
    """operator 没有 role:read → 403。

    注意：operator 能读 `/api/roles/options`（下拉框用，守卫是 menu:read），
    但读不了完整的 `/api/roles`。
    """
    resp = client.get("/api/roles", headers=operator_header)
    assert resp.status_code == 403
    assert "role:read" in resp.json()["detail"]


def test_role_options_endpoint_for_user_form(
    client: TestClient, operator_header: dict[str, str]
) -> None:
    """`/api/roles/options` 给用户编辑页的下拉框用，守卫是 menu:read。

    operator 有 menu:read，所以能拿到——即使它读不了完整角色列表。
    """
    resp = client.get("/api/roles/options", headers=operator_header)
    assert resp.status_code == 200
    data = resp.json()
    assert {r["code"] for r in data} == {"admin", "operator", "auditor", "viewer"}
    # 精简形状：只有 id/code/name/remark
    assert set(data[0].keys()) == {"id", "code", "name", "remark"}
