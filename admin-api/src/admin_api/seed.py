"""种子数据：建表 + 灌初始角色/权限/菜单/用户。

运行：uv run python -m admin_api.seed

对标前端：数据库初始化脚本 / prisma db seed。

建表走 Alembic（`alembic upgrade head`），不直接 create_all——
这样开发库、测试库、生产库的结构都由同一份迁移脚本决定，
不会出现「本地能跑线上炸了」。种子数据本身是幂等的，重复跑安全。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .core.security import hash_password
from .database import SessionLocal
from .migrate import upgrade_to_head
from .models import Menu, Permission, Role, User


@dataclass
class MenuSeed:
    """菜单种子数据。

    用具名字段而不是元组——七个元素的元组解包谁也看不懂哪个是哪个，
    加字段时也不会连带改一堆位置参数。
    """

    name: str
    path: str
    component: str
    route_name: str
    icon: str = ""
    sort: int = 0
    # 父菜单的 route_name，None 表示顶级
    parent_route: str | None = None
    # 该菜单需要的权限码
    permissions: list[str] = field(default_factory=list)


# ============================================================
# 初始数据定义
# ============================================================

PERMISSIONS = [
    ("user:read", "查看用户", "用户管理"),
    ("user:create", "创建用户", "用户管理"),
    ("user:update", "编辑用户", "用户管理"),
    ("user:delete", "删除用户", "用户管理"),
    ("menu:read", "查看菜单", "菜单管理"),
    ("menu:write", "编辑菜单", "菜单管理"),
    ("role:read", "查看角色", "角色管理"),
    ("role:write", "编辑角色", "角色管理"),
]

MENUS = [
    MenuSeed(name="工作台", path="/dashboard", component="Dashboard",
             route_name="dashboard", icon="dashboard", sort=0),
    MenuSeed(name="系统管理", path="/system", component="Layout",
             route_name="system", icon="setting", sort=1),
    MenuSeed(name="用户管理", path="/system/user", component="system/user",
             route_name="system-user", icon="user", sort=1, parent_route="system",
             permissions=["user:read", "user:create", "user:update", "user:delete"]),
    MenuSeed(name="角色管理", path="/system/role", component="system/role",
             route_name="system-role", icon="team", sort=2, parent_route="system",
             permissions=["role:read", "role:write"]),
    MenuSeed(name="菜单管理", path="/system/menu", component="system/menu",
             route_name="system-menu", icon="menu", sort=3, parent_route="system",
             permissions=["menu:read", "menu:write"]),
]

ROLES = [
    ("admin", "超级管理员", "拥有全部权限"),
    ("operator", "运营人员", "可管理用户，不能删角色"),
    ("viewer", "只读用户", "只能看"),
]


def seed(db: Session) -> None:
    """灌种子数据（幂等：已存在就跳过）。"""
    # ---- 权限 ----
    perm_map: dict[str, Permission] = {}
    for code, name, group in PERMISSIONS:
        existing = db.query(Permission).filter(Permission.code == code).first()
        if existing is None:
            existing = Permission(code=code, name=name, group=group)
            db.add(existing)
            db.flush()  # flush 拿到 id 但不提交
        perm_map[code] = existing

    # ---- 菜单 ----
    menu_map: dict[str, Menu] = {}
    for spec in MENUS:
        existing = db.query(Menu).filter(Menu.route_name == spec.route_name).first()
        if existing is None:
            existing = Menu(
                name=spec.name,
                path=spec.path,
                component=spec.component,
                route_name=spec.route_name,
                icon=spec.icon,
                sort=spec.sort,
                parent_id=0,  # 下面第二遍再修正父级
            )
            db.add(existing)
            db.flush()
        # 绑定权限。
        # 注意这是**覆盖式赋值**（不是 append）：seed 每次跑都会把菜单的权限
        # 重置成 PERMISSIONS 里声明的那一份。
        # 这是幂等的代价——如果你在管理端手动改过菜单权限码，
        # 跑一次 seed 就会被改回去。开发期可以接受，生产环境别随便跑 seed。
        existing.permissions = [perm_map[c] for c in spec.permissions if c in perm_map]
        menu_map[spec.route_name] = existing

    # 修正父子关系（第二遍，因为父菜单可能还没建）
    for spec in MENUS:
        if spec.parent_route and spec.parent_route in menu_map:
            menu_map[spec.route_name].parent_id = menu_map[spec.parent_route].id

    # ---- 角色 ----
    role_map: dict[str, Role] = {}
    for code, name, remark in ROLES:
        existing = db.query(Role).filter(Role.code == code).first()
        if existing is None:
            existing = Role(code=code, name=name, remark=remark)
            db.add(existing)
            db.flush()
        role_map[code] = existing

    # admin 拥有全部菜单
    role_map["admin"].menus = list(menu_map.values())
    # operator 拥有除「角色管理」外的菜单
    role_map["operator"].menus = [
        m for name, m in menu_map.items() if name != "system-role"
    ]
    # viewer 只有工作台
    role_map["viewer"].menus = [menu_map["dashboard"]]

    # ---- 用户 ----
    users = [
        ("admin", "admin123", "超级管理员", "admin@demo.com", ["admin"]),
        ("operator", "op123456", "运营小王", "op@demo.com", ["operator"]),
        ("viewer", "view123", "只读小李", "view@demo.com", ["viewer"]),
    ]
    for username, password, nickname, email, role_codes in users:
        existing = db.query(User).filter(User.username == username).first()
        if existing is None:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    nickname=nickname,
                    email=email,
                    is_active=True,
                    roles=[role_map[c] for c in role_codes],
                )
            )
            print(f"  + 创建用户 {username} / {password}")
        else:
            print(f"  = 用户 {username} 已存在，跳过")

    db.commit()


def main() -> None:
    """建表 + 灌数据。

    print 全部带 flush=True：Alembic 的日志走 stderr、print 走 stdout，
    管道场景下 stdout 是块缓冲的，不 flush 会出现「迁移日志」跑到
    「应用数据库迁移…」前面的错觉。
    """
    print("[seed] 应用数据库迁移…", flush=True)
    upgrade_to_head()
    print("[seed] 灌种子数据…", flush=True)
    with SessionLocal() as db:
        seed(db)
    print(
        "[seed] 完成。默认账号：admin/admin123、operator/op123456、viewer/view123",
        flush=True,
    )


if __name__ == "__main__":
    main()
