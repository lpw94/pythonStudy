"""角色管理路由。

对标前端 admin-web 的「角色管理」页：列表 + 新建 + 编辑菜单权限 + 删除。

**关键设计：权限码不是直接挂在角色上的**，而是挂在菜单上。
角色 → 菜单 → 权限码。所以「给角色授权」实际是「给角色勾选菜单」，
后端在返回角色详情时把权限码算出来（`RoleOut.permissions`）。

这也是为什么 `require_permission` 里是
`{p.code for role in user.roles for m in role.menus for p in m.permissions}`——
要走两层才能拿到权限码。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import DbSession, require_permission
from ..models import User
from ..schemas import RoleCreate, RoleOut, RoleUpdate
from ..services import (
    RoleError,
    RoleNotFoundError,
    create_role,
    delete_role,
    list_roles_out,
    update_role,
)

router = APIRouter(prefix="/api/roles", tags=["角色管理"])


@router.get("", response_model=list[RoleOut], summary="角色列表")
def api_list_roles(
    db: DbSession,
    _admin: User = Depends(require_permission("role:read")),
) -> list[RoleOut]:
    """角色列表，含每个角色推导出的权限码和用户数。"""
    return list_roles_out(db)


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED, summary="创建角色")
def api_create_role(
    payload: RoleCreate,
    db: DbSession,
    _admin: User = Depends(require_permission("role:write")),
) -> RoleOut:
    """新建角色。code 唯一且创建后不可改。"""
    try:
        return create_role(
            db,
            code=payload.code,
            name=payload.name,
            remark=payload.remark,
            menu_ids=payload.menu_ids,
        )
    except RoleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put("/{role_id}", response_model=RoleOut, summary="更新角色")
def api_update_role(
    role_id: int,
    payload: RoleUpdate,
    db: DbSession,
    _admin: User = Depends(require_permission("role:write")),
) -> RoleOut:
    """改角色名/说明，或重新勾选菜单（= 改权限）。"""
    try:
        return update_role(
            db,
            role_id,
            name=payload.name,
            remark=payload.remark,
            menu_ids=payload.menu_ids,
        )
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RoleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除角色")
def api_delete_role(
    role_id: int,
    db: DbSession,
    _admin: User = Depends(require_permission("role:write")),
) -> None:
    """删除角色。角色下还有用户时会被拒绝。"""
    try:
        delete_role(db, role_id)
    except RoleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
