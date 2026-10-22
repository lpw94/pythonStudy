"""菜单 / 权限路由：动态路由的数据源。

对标前端动态路由的两步：
1. 登录后拿菜单树 → `router.addRoute()` 注册
2. 拿权限码数组 → `hasPermission()` 控制按钮显隐

**菜单是权限的载体**：权限码挂在菜单上，角色勾选菜单即获得权限。
所以改菜单的权限码，等于间接改了所有关联角色的权限。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import CurrentUser, DbSession, require_permission
from ..models import User
from ..schemas import MenuCreate, MenuOut, MenuUpdate, PermissionOut
from ..services import (
    MenuError,
    MenuNotFoundError,
    create_menu,
    delete_menu,
    list_all_menus,
    list_all_roles,
    update_menu,
)

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


@router.get("/permissions", response_model=list[PermissionOut], summary="全部权限码")
def api_all_permissions(
    db: DbSession,
    _admin: User = Depends(require_permission("menu:read")),
) -> list[PermissionOut]:
    """系统里定义的所有权限码。

    菜单编辑页要选权限码，不能把权限码字符串硬编码在前端——
    后端加一个权限码，前端应该自动能选。
    """
    from ..services import list_all_permissions

    return list_all_permissions(db)


@router.get("/menus/flat", response_model=list[MenuOut], summary="全部菜单（平铺，不组树）")
def api_flat_menus(
    db: DbSession,
    _admin: User = Depends(require_permission("menu:read")),
) -> list[MenuOut]:
    """返回平铺的菜单列表（带 parent_id，不组装 children）。

    **什么时候用平铺**：
    - 「给角色勾菜单」这种多选场景——勾选框要一维列表，
      树形反而不好做（勾了父节点要不要连带勾子节点？）
    - 脚本/命令行批量操作

    **什么时候用树**：左侧导航渲染、动态路由注册——都需要层级关系。
    """
    from ..services import list_flat_menus

    return list_flat_menus(db)


@router.post(
    "/menus",
    response_model=MenuOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建菜单",
)
def api_create_menu(
    payload: MenuCreate,
    db: DbSession,
    _admin: User = Depends(require_permission("menu:write")),
) -> MenuOut:
    """新建菜单。route_name 必须全局唯一。"""
    try:
        return create_menu(
            db,
            name=payload.name,
            path=payload.path,
            component=payload.component,
            route_name=payload.route_name,
            icon=payload.icon,
            sort=payload.sort,
            visible=payload.visible,
            parent_id=payload.parent_id,
            permission_codes=payload.permission_codes,
        )
    except MenuError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/menus/{menu_id}", response_model=MenuOut, summary="更新菜单")
def api_update_menu(
    menu_id: int,
    payload: MenuUpdate,
    db: DbSession,
    _admin: User = Depends(require_permission("menu:write")),
) -> MenuOut:
    """改菜单（名称/路径/权限码等）。

    注意 `permission_codes` 改的是**关联角色的权限**——
    菜单的权限码是挂在菜单上的，不是直接挂用户。
    """
    try:
        return update_menu(
            db,
            menu_id,
            name=payload.name,
            path=payload.path,
            component=payload.component,
            icon=payload.icon,
            sort=payload.sort,
            visible=payload.visible,
            parent_id=payload.parent_id,
            permission_codes=payload.permission_codes,
        )
    except MenuNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except MenuError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除菜单")
def api_delete_menu(
    menu_id: int,
    db: DbSession,
    _admin: User = Depends(require_permission("menu:write")),
) -> None:
    """删除菜单。有子菜单或还有角色引用时会被拒绝。"""
    try:
        delete_menu(db, menu_id)
    except MenuNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except MenuError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/roles/options",
    summary="角色下拉选项（用户编辑页用）",
)
def api_role_options(
    db: DbSession,
    _admin: User = Depends(require_permission("menu:read")),
) -> list[dict]:
    """精简的角色列表，给「给用户分配角色」的下拉框用。

    **和 `/api/roles` 的区别**：
    - `/api/roles` 守卫 `role:read`，返回完整角色（含权限码、用户数），
      是「角色管理页」的数据源
    - `/api/roles/options` 守卫 `menu:read`，只给 id/code/name/remark，
      是「用户编辑页」的下拉框数据源

    分成两个是因为「能改用户」和「能管角色」是两种能力：
    运营人员要能给人分配角色，但不一定该看到所有角色的权限构成。

    注意：这个接口挂在 /api/ 前缀下但守卫用的是 `menu:read`，
    路径和守卫权限码对不上——这是历史设计，改动会影响已有调用方。
    """
    return [
        {"id": r.id, "code": r.code, "name": r.name, "remark": r.remark}
        for r in list_all_roles(db)
    ]
