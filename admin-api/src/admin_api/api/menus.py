"""菜单 / 权限路由：动态路由的数据源。

对标前端动态路由的两步：
1. 登录后拿菜单树 → `router.addRoute()` 注册
2. 拿权限码数组 → `hasPermission()` 控制按钮显隐
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.deps import CurrentUser, DbSession, require_permission
from ..models import User
from ..schemas import MenuOut
from ..services import list_all_menus, list_all_roles

router = APIRouter(prefix="/api", tags=["菜单与权限"])


@router.get("/auth/menus", response_model=list[MenuOut], summary="当前用户可见的菜单树")
def api_my_menus(user: CurrentUser, db: DbSession) -> list[MenuOut]:
    """返回**当前用户**能看到的菜单树。

    注意这里走的是 /api/auth/ 前缀而不是 /api/menus：
    它是「我的」视角，需要按角色过滤；
    管理端全量菜单在下面 /api/menus。
    """
    from ..services import build_profile

    return build_profile(db, user).menus


@router.get("/menus", response_model=list[MenuOut], summary="全部菜单（管理端）")
def api_all_menus(
    db: DbSession,
    _admin: User = Depends(require_permission("menu:read")),
) -> list[MenuOut]:
    """管理端用：返回所有菜单树。"""
    return list_all_menus(db)


@router.get("/roles", summary="全部角色")
def api_all_roles(
    db: DbSession,
    _admin: User = Depends(require_permission("menu:read")),
) -> list[dict]:
    """角色列表，给用户编辑页的下拉框用。"""
    return [
        {"id": r.id, "code": r.code, "name": r.name, "remark": r.remark}
        for r in list_all_roles(db)
    ]
