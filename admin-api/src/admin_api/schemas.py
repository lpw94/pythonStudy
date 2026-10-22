"""Schema 层：Pydantic 出入参定义（对标 zod schema）。

FastAPI 的核心魔法：**同一个模型既能校验入参，也能生成响应文档**。
- `model_config = ConfigDict(from_attributes=True)` 让它能从 ORM 对象读属性
  （否则 pydantic 只认 dict，不认 ORM 实例）
- 写接口时 `response_model=...` 声明返回结构，FastAPI 自动过滤多余字段 + 生成文档
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 权限 / 菜单
# ============================================================


class PermissionOut(BaseModel):
    """权限码，对标前端 `hasPermission()` 用的字符串。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    group: str = ""


class MenuOut(BaseModel):
    """菜单项输出。

    `children` 是树形结构，由 service 层组装好再返回——
    数据库里存的是平铺的 parent_id，组装成树是业务逻辑，不该由 schema 干。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    component: str = ""
    route_name: str
    icon: str = ""
    sort: int = 0
    visible: bool = True
    parent_id: int = 0
    # 这个菜单关联的权限码
    permissions: list[str] = Field(default_factory=list)
    # 子菜单，顶级菜单才有
    children: list[MenuOut] = Field(default_factory=list)


# ============================================================
# 认证
# ============================================================


class LoginRequest(BaseModel):
    """登录入参。

    Field(..., min_length=...) 是 zod 的 z.string().min() 对应物：
    校验不过直接返回 422，根本不会进业务代码。
    """

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """刷新令牌入参。"""

    refresh_token: str = Field(..., min_length=1)


class TokenPair(BaseModel):
    """登录/刷新成功后返回的令牌对。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # 访问令牌剩余秒数，前端可据此提前刷新
    expires_in: int


class ProfileOut(BaseModel):
    """当前登录用户信息 + 权限码 + 菜单树。

    这是一个「聚合响应」：前端登录后一次拿全，不用再发三个请求。
    对标前端 redux 里 login 成功后的 dispatch 一串 action。
    """

    id: int
    username: str
    nickname: str = ""
    email: str = ""
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    menus: list[MenuOut] = Field(default_factory=list)


# ============================================================
# 用户
# ============================================================


class RoleRef(BaseModel):
    """角色引用（只给 id 和 code，够前端渲染标签用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class UserOut(BaseModel):
    """用户输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str = ""
    email: str = ""
    is_active: bool = True
    roles: list[RoleRef] = Field(default_factory=list)
    created_at: datetime | None = None


class UserCreate(BaseModel):
    """创建用户入参。"""

    username: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=64)
    email: str = Field(default="", max_length=128)
    # 要给这个用户分配的角色 code 列表，如 ["operator"]
    role_codes: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """更新用户入参：所有字段可选，只传要改的。

    对标前端的 partial update——不传字段表示「不改」，
    区别于传 null 表示「清空」。
    """

    nickname: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role_codes: list[str] | None = None


class PageMeta(BaseModel):
    """分页元信息。"""

    total: int
    page: int
    page_size: int
    pages: int


class UserPage(BaseModel):
    """分页用户列表。

    对标 antd Table 的 dataSource + pagination 一起返回。
    """

    items: list[UserOut] = Field(default_factory=list)
    meta: PageMeta


# ============================================================
# 角色
# ============================================================


class RoleOut(BaseModel):
    """角色输出。

    `permissions` 是这个角色挂的菜单所衍生的权限码并集——
    前端角色编辑页要显示「这个角色实际能干什么」，
    但权限码在数据库里是挂在菜单上的，不是直接挂角色的。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    remark: str = ""
    # 该角色关联的菜单 id
    menu_ids: list[int] = Field(default_factory=list)
    # 该角色实际拥有的权限码（由菜单推导）
    permissions: list[str] = Field(default_factory=list)
    user_count: int = 0
    created_at: datetime | None = None


class RoleCreate(BaseModel):
    """创建角色入参。"""

    code: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=64)
    remark: str = Field(default="", max_length=255)
    # 要关联的菜单 id 列表
    menu_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """更新角色入参：所有字段可选，只传要改的。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    remark: str | None = Field(default=None, max_length=255)
    menu_ids: list[int] | None = None


# ============================================================
# 菜单
# ============================================================


class MenuCreate(BaseModel):
    """创建菜单入参。"""

    name: str = Field(..., min_length=1, max_length=64)
    path: str = Field(..., min_length=1, max_length=128)
    # 前端组件路径，对应 dynamic import 的键，如 "system/user"
    component: str = Field(default="", max_length=128)
    # 路由 name，必须全局唯一
    route_name: str = Field(..., min_length=1, max_length=128)
    icon: str = Field(default="", max_length=64)
    sort: int = 0
    visible: bool = True
    # 父菜单 id，0 表示顶级
    parent_id: int = 0
    # 该菜单需要的权限码
    permission_codes: list[str] = Field(default_factory=list)


class MenuUpdate(BaseModel):
    """更新菜单入参：所有字段可选，只传要改的。"""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    path: str | None = Field(default=None, min_length=1, max_length=128)
    component: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=64)
    sort: int | None = None
    visible: bool | None = None
    parent_id: int | None = None
    permission_codes: list[str] | None = None
