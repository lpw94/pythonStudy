"""用户管理路由。

对标前端 admin-web 的「用户管理」页：表格 + 分页 + 新建 + 编辑 + 删除。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.deps import DbSession, require_permission
from ..models import User
from ..repositories import get_user_by_id
from ..schemas import UserCreate, UserOut, UserPage, UserUpdate
from ..services import UserError, create_user, delete_user, list_users_page, update_user

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", response_model=UserPage, summary="用户列表（分页）")
def api_list_users(
    db: DbSession,
    _admin: User = Depends(require_permission("user:read")),
    keyword: str = Query("", description="用户名/昵称模糊搜索"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
) -> UserPage:
    """分页列出用户。

    Query(...) 是「查询参数」声明，对标 express 的 req.query。
    ge=1 / le=100 是取值范围校验，越界直接 422。
    """
    return list_users_page(db, keyword=keyword, page=page, page_size=page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
def api_create_user(
    payload: UserCreate,
    db: DbSession,
    _admin: User = Depends(require_permission("user:create")),
) -> UserOut:
    """新建用户。密码在 service 层做 bcrypt 哈希。"""
    try:
        return create_user(
            db,
            username=payload.username,
            password=payload.password,
            nickname=payload.nickname,
            email=payload.email,
            role_codes=payload.role_codes,
        )
    except UserError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/{user_id}", response_model=UserOut, summary="用户详情")
def api_get_user(
    user_id: int,
    db: DbSession,
    _admin: User = Depends(require_permission("user:read")),
) -> UserOut:
    """按 id 查用户。"""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=UserOut, summary="更新用户")
def api_update_user(
    user_id: int,
    payload: UserUpdate,
    db: DbSession,
    _admin: User = Depends(require_permission("user:update")),
) -> UserOut:
    """改用户（昵称/邮箱/密码/角色/启用状态）。

    部分更新语义：**不传的字段保持原样**，不是置空。
    前端表单只提交改动过的字段就行。
    """
    try:
        return update_user(
            db,
            user_id,
            nickname=payload.nickname,
            email=payload.email,
            is_active=payload.is_active,
            password=payload.password,
            role_codes=payload.role_codes,
        )
    except UserError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除用户")
def api_delete_user(
    user_id: int,
    db: DbSession,
    _admin: User = Depends(require_permission("user:delete")),
) -> None:
    """删除用户及其角色关联。

    204 No Content 表示成功但没有响应体。
    """
    try:
        delete_user(db, user_id)
    except UserError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
