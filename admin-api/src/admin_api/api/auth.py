"""认证相关路由：登录 / 刷新 / 当前用户。

对标前端 `src/services/auth.ts` + 登录页的 dispatch 逻辑。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..core.deps import CurrentUser, DbSession
from ..core.security import decode_token
from ..schemas import LoginRequest, ProfileOut, RefreshRequest, TokenPair
from ..services import AuthError, build_profile, login

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenPair, summary="账号密码登录")
def api_login(payload: LoginRequest, db: DbSession) -> TokenPair:
    """登录成功返回 access + refresh 两个令牌。

    失败统一返回 401，且不区分「用户不存在」和「密码错误」。
    """
    try:
        return login(db, payload.username, payload.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/refresh", response_model=TokenPair, summary="用 refresh token 换新令牌")
def api_refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """刷新令牌。

    校验 refresh token 的签名/有效期/类型 → 取用户 → 签发新的一对令牌。
    """
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期"
        )

    from ..core.security import create_access_token, create_refresh_token
    from ..repositories import get_user_by_id

    user = get_user_by_id(db, int(claims.get("sub", 0)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return TokenPair(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id, user.username),
        expires_in=60 * 60 * 12,
    )


@router.get("/me", response_model=ProfileOut, summary="当前用户 + 权限 + 菜单")
def api_me(user: CurrentUser, db: DbSession) -> ProfileOut:
    """返回当前登录用户的完整档案。

    前端登录后调一次，把 roles / permissions / menus 塞进 store。
    """
    return build_profile(db, user)
