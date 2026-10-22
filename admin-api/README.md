# admin-api · 权限路由后端（Python 阶段 3 学习项目）

给 **admin-web**（antd 权限路由系统）配的后端。用 Python 重写一遍后端该有的样子，
每个概念都标注了 **对标你熟悉的前端写法**。

## 技术栈对照

| 前端 | Python | 说明 |
| --- | --- | --- |
| express / koa | **FastAPI** | 装饰器即路由，`async def` 写异步 |
| zod | **Pydantic v2** | 运行时校验 + 自动生成 OpenAPI 文档 |
| prisma / typeorm | **SQLAlchemy 2.0** | ORM，`select()` 风格查询 |
| prisma migrate | **Alembic** | 数据库版本化迁移，upgrade / downgrade |
| jsonwebtoken | **PyJWT** | 签发/校验 access + refresh token |
| bcrypt | **bcrypt**（直接用，不用 passlib） | 密码哈希 |
| express 中间件 | **Depends** | 依赖注入，认证/鉴权靠它 |
| eslint + prettier | **Ruff** | lint + format 一个工具搞定 |
| jest / vitest | **pytest** | fixture 机制是核心 |

## 分层结构

```
src/admin_api/
├── config.py         # 配置（.env → 带类型的 Settings）
├── database.py       # engine / SessionLocal / Base / get_db
├── migrate.py        # 把 Alembic 包成可调用的函数
├── models.py         # SQLAlchemy ORM 模型（对标 prisma schema）
├── schemas.py        # Pydantic 出入参（对标 zod schema）
├── seed.py           # 种子数据（幂等）
├── core/
│   ├── security.py   # 密码哈希 + JWT 签发校验
│   └── deps.py       # 依赖：当前用户 / 权限校验
├── repositories/     # 数据访问层（只碰数据库）
├── services/         # 业务逻辑层（只管规则，不碰 HTTP）
└── api/
    ├── auth.py       # 登录 / 刷新 / 登出
    ├── users.py      # 用户 CRUD
    └── menus.py      # 菜单与权限（动态路由来源）

alembic.ini            # Alembic 配置
migrations/            # 迁移脚本（env.py + versions/）
  ├── env.py
  └── versions/
    └── 55281caab24c_init_schema.py
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

# 2) 应用迁移 + 灌种子数据
uv run python -m admin_api.seed

# 3) 起服务
uv run uvicorn admin_api.main:app --reload --port 8020
```

打开 <http://127.0.0.1:8020/docs> 就是自动生成的 **Swagger UI**——
FastAPI 会根据类型注解自动生成接口文档，不用手写。

> 端口用 **8020**：`admin-web-demo` 的 `VITE_API_BASE` 和 CORS 白名单都按这个配。

## 数据库迁移（Alembic）

表结构由版本化脚本管理，开发库 / 测试库 / 生产库跑的是同一份迁移。

```bash
uv run alembic upgrade head                              # 应用到最新版本
uv run alembic downgrade -1                              # 回滚一版
uv run alembic revision --autogenerate -m "给 users 加字段"  # 按模型差异生成新迁移
uv run alembic current                                   # 当前版本
uv run alembic history                                   # 版本历史
```

改 `models.py` 之后的固定流程：

1. 改模型
2. `alembic revision --autogenerate -m "..."` 生成迁移
3. **人工检查**生成的脚本（改列名、改约束这类 autogenerate 识别不出来）
4. `alembic upgrade head` 应用
5. 提交迁移文件

`seed.py` 内部调的是 `upgrade_to_head()`，所以跑 seed 会自动把表结构升到最新。

> `alembic.ini` 必须保持纯 ASCII：Alembic 用 **locale 编码**读它
> （`configparser.read(..., encoding="locale")`），中文 Windows 上是 GBK，
> 注释里写中文会直接 `UnicodeDecodeError` 崩掉。

## 测试

```bash
uv run pytest -q
```

测试库是**内存 SQLite**，建表走同一份 Alembic 迁移脚本（不是 `create_all`）——
这样测试过的表结构就是生产会跑的结构。

清理用 `downgrade` 到 base 而不是 `drop_all`：`drop_all` 不碰 `alembic_version`，
版本号残留会让下一个测试的 upgrade 变成空操作，表根本没建出来。

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
