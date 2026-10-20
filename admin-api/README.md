# admin-api · 权限路由后端（Python 阶段 3 学习项目）

给 **admin-web**（antd 权限路由系统）配的后端。用 Python 重写一遍后端该有的样子，
每个概念都标注了 **对标你熟悉的前端写法**。

## 技术栈对照

| 前端 | Python | 说明 |
| --- | --- | --- |
| express / koa | **FastAPI** | 装饰器即路由，`async def` 写异步 |
| zod | **Pydantic v2** | 运行时校验 + 自动生成 OpenAPI 文档 |
| prisma / typeorm | **SQLAlchemy 2.0** | ORM，`select()` 风格查询 |
| jsonwebtoken | **PyJWT** | 签发/校验 access + refresh token |
| bcrypt | **passlib[bcrypt]** | 密码哈希 |
| express 中间件 | **Depends** | 依赖注入，认证/鉴权靠它 |
| eslint + prettier | **Ruff** | lint + format 一个工具搞定 |
| jest / vitest | **pytest** | fixture 机制是核心 |

## 分层结构

```
src/admin_api/
├── config.py         # 配置（.env → 带类型的 Settings）
├── database.py       # engine / SessionLocal / Base / get_db
├── models.py         # SQLAlchemy ORM 模型（对标 prisma schema）
├── schemas.py        # Pydantic 出入参（对标 zod schema）
├── core/
│   ├── security.py   # 密码哈希 + JWT 签发校验
│   └── deps.py       # 依赖：当前用户 / 权限校验
├── repositories/     # 数据访问层（只碰数据库）
├── services/         # 业务逻辑层（只管规则，不碰 HTTP）
└── api/
    ├── auth.py       # 登录 / 刷新 / 登出
    ├── users.py      # 用户 CRUD
    └── menus.py      # 菜单与权限（动态路由来源）
```

**为什么分四层**：和你前端项目一致——
`api` 只管「收参数 + 出响应」，`services` 只管「业务规则」，
`repositories` 只管「怎么拿数据」，`schemas` 定义「数据长什么样」。
换数据库只动 repositories，换传输协议（HTTP → gRPC）只动 api。

## 运行

```bash
cd admin-api

# 1) 安装依赖 + 建虚拟环境（首次）
uv sync

# 2) 建表 + 灌种子数据
uv run python -m admin_api.seed

# 3) 起服务
uv run uvicorn admin_api.main:app --reload --port 8000
```

打开 <http://127.0.0.1:8000/docs> 就是自动生成的 **Swagger UI**——
FastAPI 会根据类型注解自动生成接口文档，不用手写。

## 测试

```bash
uv run pytest -q
```

## 核心接口

| 方法 | 路径 | 说明 | 对标前端 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 账号密码换 token | 登录页的 `login()` action |
| POST | `/api/auth/refresh` | 刷新令牌 | axios 响应拦截器里的 401 续期逻辑 |
| GET | `/api/auth/me` | 当前用户 + 权限码 | `useUserStore().profile` |
| GET | `/api/auth/menus` | **当前用户可见的菜单树** | 动态路由 `addRoute()` 的数据源 |
| GET/POST | `/api/users` | 用户列表 / 创建 | 后台用户管理页表格 |
| GET/PUT/DELETE | `/api/users/{id}` | 用户详情 / 改 / 删 | 同上 |

## 权限模型（和 admin-web 对齐）

```
user  ──< user_roles >──  role  ──< role_menus >──  menu
                                                 └──< menu_permissions >── permission
```

- **user**：账号、密码哈希、是否启用
- **role**：角色（admin / operator / viewer）
- **permission**：权限码（`user:create`、`menu:delete`…），对应前端的 `hasPermission()`
- **menu**：菜单项（路由 name / path / component / 权限码 / 排序）
- 关联表用 `Table(..., ForeignKey(...))` 定义，对标 prisma 的多对多隐式关系

登录后前端拿两样东西：**权限码数组**（控制按钮显隐）和**菜单树**（控制左侧导航 + 动态路由）。
这两个都由后端算好下发，前端不自己拼——这是权限系统的核心原则。

## 安全提示

- `config.py` 里 `jwt_secret` 是开发默认值，**生产必须用环境变量覆盖**
- 密码用 bcrypt 哈希入库，数据库里永远不存明文
- `.env` 已被 `.gitignore` 忽略，`.env.example` 是可提交的模板
