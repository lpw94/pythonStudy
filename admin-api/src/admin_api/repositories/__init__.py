"""仓储层：只负责「怎么从数据库拿数据」。

对标前端的 `src/services/*.ts` 里那部分纯数据请求。
约定：
- 每个函数一个明确的数据获取动作，不写业务判断
- 业务规则（能不能删、要不要通知别人）放 services 层
- 返回 ORM 对象或标量，不返回 HTTP 相关的东西
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Menu, Permission, Role, User

# ============================================================
# 用户
# ============================================================


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """按 id 查用户。"""
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    """按用户名查用户（登录用）。

    select(...).where(...) 是 SQLAlchemy 2.0 的新写法，
    对标 prisma 的 `prisma.user.findUnique({ where: { username } })`。
    """
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def list_users(
    db: Session,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """分页查用户列表，返回 (当前页数据, 总条数)。

    offset/limit 是 SQL 的分页写法，对标 prisma 的 skip/take。
    """
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    if keyword:
        # %keyword% 是模糊匹配（LIKE），对标 prisma 的 contains
        like = f"%{keyword}%"
        cond = User.username.like(like) | User.nickname.like(like)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.execute(count_stmt).scalar_one()
    # 排序：按 id 倒序（新的在前），对标 orderBy: { id: 'desc' }
    stmt = stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).scalars().all()
    return list(rows), int(total)


def username_exists(db: Session, username: str, *, exclude_id: int = 0) -> bool:
    """用户名是否已被占用。

    exclude_id > 0 表示「排除自己」（改用户名时用）。
    """
    stmt = select(func.count()).select_from(User).where(User.username == username)
    if exclude_id:
        stmt = stmt.where(User.id != exclude_id)
    return bool(db.execute(stmt).scalar_one())


# ============================================================
# 角色 / 权限
# ============================================================


def list_roles(db: Session) -> list[Role]:
    """所有角色。"""
    stmt = select(Role).order_by(Role.id)
    return list(db.execute(stmt).scalars().all())


def get_roles_by_codes(db: Session, codes: Sequence[str]) -> list[Role]:
    """按 code 批量查角色。

    `in_()` 对应 SQL 的 IN (...)，对标 prisma 的 `in: [...]`。
    """
    if not codes:
        return []
    stmt = select(Role).where(Role.code.in_(list(codes)))
    return list(db.execute(stmt).scalars().all())


def list_permissions(db: Session) -> list[Permission]:
    """所有权限码。"""
    stmt = select(Permission).order_by(Permission.group, Permission.id)
    return list(db.execute(stmt).scalars().all())


# ============================================================
# 菜单
# ============================================================


def list_menus(db: Session) -> list[Menu]:
    """所有菜单（平铺，未组树）。"""
    stmt = select(Menu).order_by(Menu.sort, Menu.id)
    return list(db.execute(stmt).scalars().all())


def get_menus_by_ids(db: Session, menu_ids: Sequence[int]) -> list[Menu]:
    """按 id 批量查菜单。"""
    if not menu_ids:
        return []
    stmt = select(Menu).where(Menu.id.in_(list(menu_ids))).order_by(Menu.sort, Menu.id)
    return list(db.execute(stmt).scalars().all())
