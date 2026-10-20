"""依赖层：FastAPI 的 Depends。

对标前端：
- `get_current_user` ≈ axios 请求拦截器里「带上 token + 处理 401」
- `require_permission` ≈ 路由守卫 / 按钮级权限判断

关键点：依赖是**可组合**的——路由声明一次，就自动获得认证 + 鉴权。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.security import decode_token
from ..database import get_db
from ..models import User
from ..repositories import get_user_by_id

# HTTPBearer 会从 Authorization: Bearer xxx 里取出令牌。
# auto_error=False：令牌缺失时不自动抛 401，交给我们自己处理（要区分「没登录」和「令牌无效」）
bearer_scheme = HTTPBearer(auto_error=False)

# 依赖别名：Annotated[Session, Depends(get_db)] 写一次到处用，
# 比每处都写 db: Session = Depends(get_db) 简洁
DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_current_user(
    db: DbSession,
    credentials: BearerToken,
) -> User:
    """取出当前登录用户。

    流程：取令牌 → 校验签名/有效期/类型 → 取 user_id → 查库 → 返回用户。
    任何一步失败都抛 401（未认证）。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub", 0))
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*required: str) -> Callable[[User], User]:
    """生成一个「需要指定权限码」的依赖。

    用法：
    ```python
    @router.delete("/{user_id}")
    def delete_user(user_id: int, _: User = Depends(require_permission("user:delete"))):
        ...
    ```
    工厂函数返回依赖——这是 FastAPI 里做「参数化鉴权」的标准写法，
    对标前端封装一个 `withPermission('user:delete')(handler)` 的 HOC。

    超级管理员（admin 角色）直接放行。
    """
    needed = set(required)

    def _checker(user: CurrentUser) -> User:
        if "admin" in {r.code for r in user.roles}:
            return user
        owned = {p.code for role in user.roles for m in role.menus for p in m.permissions}
        if not needed.issubset(owned):
            missing = ", ".join(sorted(needed - owned))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{missing}",
            )
        return user

    return _checker
