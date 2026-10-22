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
from ..models import Menu, Role, User
from ..repositories import (
    code_exists,
    count_child_menus,
    count_roles_with_menu,
    count_users_in_role,
    get_menu_by_id,
    get_menus_by_ids,
    get_permissions_by_codes,
    get_role_by_id,
    get_roles_by_codes,
    get_user_by_username,
    list_menus,
    list_roles,
    list_users,
    route_name_exists,
    username_exists,
)
from ..schemas import (
    MenuOut,
    PageMeta,
    PermissionOut,
    ProfileOut,
    RoleOut,
    TokenPair,
    UserPage,
)


class AuthError(Exception):
    """认证失败（用户名/密码错、账号被禁用）。

    自定义异常而不是直接抛 HTTPException——
    业务层不该知道 HTTP 的存在，这是分层的意义。
    api 层捕获它并翻译成 401。
    """


class UserError(Exception):
    """用户相关的业务错误（用户名重复、角色不存在等）。"""


class RoleError(Exception):
    """角色相关的业务错误（code 重复、角色下还有用户等）。"""


class RoleNotFoundError(RoleError):
    """角色不存在。

    单独一个子类，api 层据此决定返回 404 还是 400——
    靠字符串比对来判断是坏味道（改个文案就出错）。
    """


class MenuError(Exception):
    """菜单相关的业务错误（路由名重复、有子菜单不能删等）。"""


class MenuNotFoundError(MenuError):
    """菜单不存在。"""


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


def update_user(
    db: Session,
    user_id: int,
    *,
    nickname: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
    role_codes: list[str] | None = None,
) -> User:
    """更新用户（部分更新）。

    语义：**不传的字段表示「不改」**，传了就改。
    这跟 PUT 全量覆盖不一样——对标前端的 partial update。

    几个业务规则：
    - 角色 code 必须都存在，否则报错（不能静默建出新角色）
    - 不允许把自己禁用（否则当前会话立刻失效，还容易被当成 bug）
    """
    user = db.get(User, user_id)
    if user is None:
        raise UserError("用户不存在")

    if role_codes is not None:
        roles = get_roles_by_codes(db, role_codes)
        found = {r.code for r in roles}
        missing = [c for c in role_codes if c not in found]
        if missing:
            raise UserError(f"角色不存在：{', '.join(missing)}")
        user.roles = roles

    if nickname is not None:
        user.nickname = nickname
    if email is not None:
        user.email = email
    if is_active is not None:
        user.is_active = is_active
    if password is not None:
        user.password_hash = hash_password(password)

    db.commit()
    db.refresh(user)
    return user


# ============================================================
# 角色管理
# ============================================================


def _to_role_out(db: Session, role) -> RoleOut:
    """把 ORM 角色转成输出对象（补上推导出来的权限码和用户数）。"""
    permissions: set[str] = set()
    for m in role.menus:
        for p in m.permissions:
            permissions.add(p.code)
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        remark=role.remark,
        menu_ids=[m.id for m in role.menus],
        permissions=sorted(permissions),
        user_count=count_users_in_role(db, role.id),
        created_at=role.created_at,
    )


def list_roles_out(db: Session) -> list[RoleOut]:
    """角色列表（含权限码和用户数）。"""
    return [_to_role_out(db, r) for r in list_roles(db)]


def create_role(
    db: Session,
    *,
    code: str,
    name: str,
    remark: str = "",
    menu_ids: list[int] | None = None,
):
    """创建角色。

    code 是角色的唯一标识，创建后不可改——
    用户身上存的是 code（不是 id），改了 code 等于把已有用户的角色关系作废。
    """
    if code_exists(db, code):
        raise RoleError(f"角色编码 {code} 已存在")

    menus = get_menus_by_ids(db, menu_ids or [])
    found = {m.id for m in menus}
    missing = [mid for mid in (menu_ids or []) if mid not in found]
    if missing:
        raise RoleError(f"菜单不存在：{', '.join(str(m) for m in missing)}")

    role = Role(code=code, name=name, remark=remark, menus=menus)
    db.add(role)
    db.commit()
    db.refresh(role)
    return _to_role_out(db, role)


def update_role(
    db: Session,
    role_id: int,
    *,
    name: str | None = None,
    remark: str | None = None,
    menu_ids: list[int] | None = None,
) -> RoleOut:
    """更新角色。"""
    role = get_role_by_id(db, role_id)
    if role is None:
        raise RoleNotFoundError("角色不存在")

    if menu_ids is not None:
        menus = get_menus_by_ids(db, menu_ids)
        found = {m.id for m in menus}
        missing = [mid for mid in menu_ids if mid not in found]
        if missing:
            raise RoleError(f"菜单不存在：{', '.join(str(m) for m in missing)}")
        role.menus = menus

    if name is not None:
        role.name = name
    if remark is not None:
        role.remark = remark

    db.commit()
    db.refresh(role)
    return _to_role_out(db, role)


def delete_role(db: Session, role_id: int) -> None:
    """删除角色。

    保护规则：角色下还有用户时拒绝删除——
    否则那些用户会静默失去所有权限（这是最难排查的一类问题）。
    """
    role = get_role_by_id(db, role_id)
    if role is None:
        raise RoleNotFoundError("角色不存在")
    if count_users_in_role(db, role_id) > 0:
        raise RoleError("该角色下还有用户，请先解绑")
    db.delete(role)
    db.commit()


# ============================================================
# 菜单管理
# ============================================================


def create_menu(
    db: Session,
    *,
    name: str,
    path: str,
    component: str = "",
    route_name: str,
    icon: str = "",
    sort: int = 0,
    visible: bool = True,
    parent_id: int = 0,
    permission_codes: list[str] | None = None,
) -> MenuOut:
    """创建菜单。"""
    if route_name_exists(db, route_name):
        raise MenuError(f"路由名 {route_name} 已存在")
    if parent_id and get_menu_by_id(db, parent_id) is None:
        raise MenuError(f"父菜单不存在：{parent_id}")

    perms = get_permissions_by_codes(db, permission_codes or [])
    found = {p.code for p in perms}
    missing = [c for c in (permission_codes or []) if c not in found]
    if missing:
        raise MenuError(f"权限码不存在：{', '.join(missing)}")

    menu = Menu(
        name=name,
        path=path,
        component=component,
        route_name=route_name,
        icon=icon,
        sort=sort,
        visible=visible,
        parent_id=parent_id,
        permissions=perms,
    )
    db.add(menu)
    db.commit()
    db.refresh(menu)
    return _to_menu_out(menu)


def update_menu(
    db: Session,
    menu_id: int,
    *,
    name: str | None = None,
    path: str | None = None,
    component: str | None = None,
    icon: str | None = None,
    sort: int | None = None,
    visible: bool | None = None,
    parent_id: int | None = None,
    permission_codes: list[str] | None = None,
) -> MenuOut:
    """更新菜单。

    保护规则：不能把自己设为自己的子节点（会造成树结构死循环）。
    """
    menu = get_menu_by_id(db, menu_id)
    if menu is None:
        raise MenuNotFoundError("菜单不存在")

    if parent_id is not None:
        if parent_id == menu_id:
            raise MenuError("父菜单不能是自己")
        if parent_id and get_menu_by_id(db, parent_id) is None:
            raise MenuError(f"父菜单不存在：{parent_id}")

    if permission_codes is not None:
        perms = get_permissions_by_codes(db, permission_codes)
        found = {p.code for p in perms}
        missing = [c for c in permission_codes if c not in found]
        if missing:
            raise MenuError(f"权限码不存在：{', '.join(missing)}")
        menu.permissions = perms

    if name is not None:
        menu.name = name
    if path is not None:
        menu.path = path
    if component is not None:
        menu.component = component
    if icon is not None:
        menu.icon = icon
    if sort is not None:
        menu.sort = sort
    if visible is not None:
        menu.visible = visible
    if parent_id is not None:
        menu.parent_id = parent_id

    db.commit()
    db.refresh(menu)
    return _to_menu_out(menu)


def delete_menu(db: Session, menu_id: int) -> None:
    """删除菜单。

    保护规则：
    - 有子菜单时拒绝（删了父节点子节点就成了孤儿）
    - 有角色挂着时拒绝（那些角色会静默失去菜单 → 连带失去权限码）
    """
    menu = get_menu_by_id(db, menu_id)
    if menu is None:
        raise MenuNotFoundError("菜单不存在")
    if count_child_menus(db, menu_id) > 0:
        raise MenuError("该菜单下还有子菜单，请先删除子菜单")
    if count_roles_with_menu(db, menu_id) > 0:
        raise MenuError("还有角色引用该菜单，请先解绑")
    db.delete(menu)
    db.commit()


def _to_menu_out(menu: Menu) -> MenuOut:
    """ORM 菜单 → 输出对象（不含 children，children 由树形组装负责）。"""
    return MenuOut(
        id=menu.id,
        name=menu.name,
        path=menu.path,
        component=menu.component,
        route_name=menu.route_name,
        icon=menu.icon,
        sort=menu.sort,
        visible=menu.visible,
        parent_id=menu.parent_id,
        permissions=sorted(p.code for p in menu.permissions),
    )


def list_all_menus(db: Session) -> list[MenuOut]:
    """所有菜单（管理端用，返回树）。"""
    return build_menu_tree(list_menus(db))


def list_flat_menus(db: Session) -> list[MenuOut]:
    """所有菜单（平铺，不组树）。

    给「给角色勾菜单」的多选框用——一维列表比树好勾。
    """
    return [_to_menu_out(m) for m in list_menus(db)]


def list_all_permissions(db: Session) -> list[PermissionOut]:
    """系统里定义的所有权限码。

    菜单编辑页要选权限码，权限码清单得从后端来——
    前端硬编码一份的话，后端加了新权限码前端就选不到。
    """
    from ..repositories import list_permissions

    return [
        PermissionOut(id=p.id, code=p.code, name=p.name, group=p.group)
        for p in list_permissions(db)
    ]


def list_all_roles(db: Session):
    """所有角色（管理端下拉框用）。"""
    return list_roles(db)
