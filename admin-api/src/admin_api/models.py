"""ORM 模型层：SQLAlchemy 表结构定义。

对标 prisma/schema.prisma：
```prisma
model User {
  id       Int      @id @default(autoincrement())
  username String   @unique
}
```
换成 SQLAlchemy 2.0 就是下面这种写法。

命名约定（和 prisma 一致）：
- 表名用复数 snake_case：`users` / `roles` / `menus`
- 外键字段名 `<关联表单数>_id`：`user_id` / `role_id`
- 中间表（多对多）用 `<a>_<b>` 命名：`user_roles` / `role_menus`
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """当前 UTC 时间（带时区）。

    用 datetime.now(timezone.utc) 而不是 utcnow()（已废弃）。
    统一存 UTC，读取时再转本地时间——对标后端一律存 UTC 的通行做法。
    """
    return datetime.now(UTC)


# ============================================================
# 关联表（多对多）
# 纯「关系表」，没有额外字段，所以直接用 Table() 定义，不需要 ORM 类。
# 对标 prisma 的显式中间表写法。
# ============================================================

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_menus = Table(
    "role_menus",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("menu_id", Integer, ForeignKey("menus.id", ondelete="CASCADE"), primary_key=True),
)

menu_permissions = Table(
    "menu_permissions",
    Base.metadata,
    Column("menu_id", Integer, ForeignKey("menus.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ============================================================
# 主表
# ============================================================


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 存哈希不是明文！长度 255 是 bcrypt 哈希的固定长度
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    # relationship：声明 ORM 层面的关联，懒加载
    # secondary 指定中间表；对标 prisma 的 `roles UserRole[]`
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Role(Base):
    """角色表。"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles, back_populates="roles", lazy="selectin"
    )
    menus: Mapped[list[Menu]] = relationship(
        secondary=role_menus, back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.code!r}>"


class Permission(Base):
    """权限码表：定义系统里有哪些「操作权限」。

    权限码是字符串约定（不是 id），前端 `hasPermission('user:create')` 靠它判断。
    对标前端：路由 meta 里配的 permission 字符串。
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 分组名，前端权限管理页按它分栏显示
    group: Mapped[str] = mapped_column(String(64), default="")

    menus: Mapped[list[Menu]] = relationship(
        secondary=menu_permissions, back_populates="permissions", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Permission code={self.code!r}>"


class Menu(Base):
    """菜单表：既是左侧导航项，也是前端动态路由的数据源。

    树形结构用 `parent_id` 自关联（指向自己的 id）表达，
    对标 prisma 的 `parentId` 自引用 + 前端递归渲染。
    """

    __tablename__ = "menus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 路由 path，对应前端 router 的 path
    path: Mapped[str] = mapped_column(String(128), nullable=False)
    # 前端组件路径，对应 dynamic import 的键，如 "system/user"
    component: Mapped[str] = mapped_column(String(128), default="")
    # 路由 name，必须唯一，前端 addRoute 用它做标识
    route_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="")
    # 排序值，小的在前
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 是否在左侧导航显示（有些路由只做跳转，不显示菜单）
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 父菜单 id，0 表示顶级
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menus.id", ondelete="CASCADE"), default=0, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_menus, back_populates="menus", lazy="selectin"
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary=menu_permissions, back_populates="menus", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Menu id={self.id} route_name={self.route_name!r}>"
