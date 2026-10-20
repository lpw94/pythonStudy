"""服务层：业务规则。

对标前端 `src/services/` 里的业务函数（区别于纯请求的 repositories）。

这一层做三件事：
1. 权限判定（这个用户能不能做这个操作）
2. 数据组装（把平铺的菜单组装成树、把多表数据聚合成一个响应）
3. 事务边界（多个写操作要么都成功要么都回滚）
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from ..models import Menu, User
from ..repositories import (
    get_menus_by_ids,
    get_roles_by_codes,
    get_user_by_username,
    list_menus,
    list_roles,
    list_users,
    username_exists,
)
from ..schemas import MenuOut, PageMeta, ProfileOut, TokenPair, UserPage


class AuthError(Exception):
    """认证失败（用户名/密码错、账号被禁用）。

    自定义异常而不是直接抛 HTTPException——
    业务层不该知道 HTTP 的存在，这是分层的意义。
    api 层捕获它并翻译成 401。
    """


class UserError(Exception):
    """用户相关的业务错误（用户名重复、角色不存在等）。"""


# ============================================================
# 认证
# ============================================================


def login(db: Session, username: str, password: str) -> TokenPair:
    """账号密码换令牌对。"""
    user = get_user_by_username(db, username)
    # 用户不存在和密码错误返回同一个错误，避免泄露「哪些用户名存在」
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("用户名或密码错误")
    if not user.is_active:
        raise AuthError("账号已被禁用")

    return TokenPair(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id, user.username),
        expires_in=60 * 60 * 12,
    )


def build_profile(db: Session, user: User) -> ProfileOut:
    """把用户 + 角色 + 权限 + 菜单树组装成一个响应对象。

    关键点：**权限码和菜单都从用户关联的角色推导**，
    角色 → 菜单 → 权限，用户直接挂权限反而不符合角色模型。
    """
    role_codes = [r.code for r in user.roles]
    # 收集该用户所有角色能看到的菜单 id
    menu_ids: set[int] = set()
    for role in user.roles:
        for m in role.menus:
            menu_ids.add(m.id)

    menus = get_menus_by_ids(db, list(menu_ids))
    menu_tree = build_menu_tree(menus)

    # 权限码 = 该用户所有菜单关联的权限的并集
    permissions: set[str] = set()
    for m in menus:
        for p in m.permissions:
            permissions.add(p.code)

    return ProfileOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        email=user.email,
        roles=role_codes,
        permissions=sorted(permissions),
        menus=menu_tree,
    )


def build_menu_tree(menus: list[Menu]) -> list[MenuOut]:
    """把平铺的菜单列表组装成树。

    两步走（对标前端的树形数据处理）：
    1. 先把每个菜单转成 MenuOut，建立 id → 节点的映射
    2. 再遍历一次，把子节点塞到父节点下
    """
    nodes: dict[int, MenuOut] = {}
    for m in menus:
        nodes[m.id] = MenuOut(
            id=m.id,
            name=m.name,
            path=m.path,
            component=m.component,
            route_name=m.route_name,
            icon=m.icon,
            sort=m.sort,
            visible=m.visible,
            parent_id=m.parent_id,
            permissions=sorted(p.code for p in m.permissions),
        )

    roots: list[MenuOut] = []
    for m in menus:
        node = nodes[m.id]
        parent = nodes.get(m.parent_id)
        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)
    return roots


# ============================================================
# 用户管理
# ============================================================


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    nickname: str = "",
    email: str = "",
    role_codes: list[str] | None = None,
) -> User:
    """创建用户。"""
    if username_exists(db, username):
        raise UserError(f"用户名 {username} 已存在")

    roles = get_roles_by_codes(db, role_codes or [])
    user = User(
        username=username,
        password_hash=hash_password(password),
        nickname=nickname or username,
        email=email,
        roles=roles,
    )
    db.add(user)
    db.commit()  # 提交事务
    db.refresh(user)  # 重新读一遍，拿到数据库生成的 id
    return user


def list_users_page(
    db: Session, *, keyword: str = "", page: int = 1, page_size: int = 20
) -> UserPage:
    """分页查用户，包装成前端要的形状（含 meta）。"""
    rows, total = list_users(db, keyword=keyword, page=page, page_size=page_size)
    pages = (total + page_size - 1) // page_size
    return UserPage(
        items=rows,
        meta=PageMeta(total=total, page=page, page_size=page_size, pages=pages),
    )


def delete_user(db: Session, user_id: int) -> None:
    """删除用户。"""
    user = db.get(User, user_id)
    if user is None:
        raise UserError("用户不存在")
    db.delete(user)
    db.commit()


def list_all_menus(db: Session) -> list[MenuOut]:
    """所有菜单（管理端用，返回树）。"""
    return build_menu_tree(list_menus(db))


def list_all_roles(db: Session):
    """所有角色（管理端下拉框用）。"""
    return list_roles(db)
