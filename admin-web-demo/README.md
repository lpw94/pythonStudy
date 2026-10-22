# admin-web-demo

`D:\workspace\admin-web`（公司真实项目）的**替身演示工程**。只做结构对标，不做代码合并、不改动原项目任何文件。

演示的是「登录 → 权限码 → 动态菜单路由 → 按钮级权限」这条完整链路，
后端是本仓库的 [`admin-api`](../admin-api)（FastAPI + JWT + RBAC）。

## 技术栈

| 选型 | 版本 | 说明 |
| --- | --- | --- |
| React | 18 | 函数组件 + Hooks |
| Vite | 5 | 开发服务器，Windows 下需显式绑 `127.0.0.1` |
| antd | 5 | 表格 / 表单 / 树 |
| react-router-dom | 6 | `createBrowserRouter` 数据路由 |
| TypeScript | strict | `noUnusedLocals` 会抓重构残留 |

## 目录

```
src/
├── services/
│   ├── token.ts      双令牌存取（access + refresh）
│   ├── request.ts    fetch 封装：Bearer 注入 / 401 刷新重放 / 刷新锁
│   ├── api.ts        后端接口封装
│   └── notify.ts     antd message 桥接（静态方法拿不到主题 context）
├── store/auth.tsx    登录态 Context（含 initializing 防刷新闪烁）
├── access/index.ts   hasPermission() —— 按钮级权限
├── router/index.tsx  COMPONENT_MAP + buildRoutes() 从菜单树生成路由
├── components/AppLayout.tsx  侧边栏菜单（由后端 menus 驱动）
└── pages/            login / dashboard / system(user, role, menu)
```

## 跑起来

```bash
# 1. 后端（另开终端）
cd ../admin-api
.venv/Scripts/python.exe -m uvicorn admin_api.main:app --host 127.0.0.1 --port 8020

# 2. 前端
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。

**端口必须是 5173** —— `admin-api` 的 CORS 白名单只放了 5173，换端口要改后端 `.env` 的 `CORS_ORIGINS`。

## 三个管理页

| 页面 | 路径 | 需要的权限码 | 能做什么 |
| --- | --- | --- | --- |
| 用户管理 | `/system/user` | `user:read/create/update/delete` | 表格 + 分页 + 新建 + 编辑 + 删除 |
| 角色管理 | `/system/role` | `role:read` / `role:write` | 列表 + 新建 + 勾菜单授权 + 删除 |
| 菜单管理 | `/system/menu` | `menu:read` / `menu:write` | 树形展示 + 新建 + 编辑 + 删除 |

**授权 = 勾菜单**。权限码挂在菜单上，不直接挂角色。角色编辑页提交的是 `menu_ids`，
后端再从菜单推导出的权限码回传。所以「授权」这个动作在 UI 上就是勾选菜单。

## 三个内置账号

| 账号 | 密码 | 角色 | 能看到什么 |
| --- | --- | --- | --- |
| `admin` | `admin123` | admin | 全部菜单 + 8 个权限码 |
| `operator` | `op123456` | operator | 缺「角色管理」菜单 + 6 个权限码 |
| `viewer` | `view123` | viewer | 仅工作台 + **0 个**权限码 |

灌种子数据：`cd ../admin-api && .venv/Scripts/python.exe -m admin_api.seed`（幂等）。

## 权限路由是怎么跑的

1. 登录拿到 `access_token` + `refresh_token`，存 localStorage。
2. `GET /api/auth/me` 拿到 `roles[]`、`permissions[]`、`menus[]`（树）。
3. `buildRoutes()` 遍历菜单树，用 `COMPONENT_MAP` 把 `component` 字符串映射到本地组件。
   **查不到组件的路由根本不注册** —— 地址栏手输也进不去。
4. 按钮显隐走 `hasPermission(permissions, 'user:delete')`。

> 前端藏按钮只是体验。真正的安全边界在后端 `require_permission`：
> 绕过前端直接 `DELETE /api/users/1`，viewer 依然收到 `403 {"detail":"缺少权限：user:delete"}`。

## 五个坑

- **Vite 在 Windows 默认只绑 `::1`**，`127.0.0.1:5173` 连不上。`vite.config.ts` 里显式设 `server.host = '127.0.0.1'`。
- 本机有 `http_proxy` 环境变量，`curl` 测本地端口要加 `--noproxy '*'`。
- `.tsx` 里 `{cond ? 'a' : 'b'}` 后面紧跟 `}` 会报 TS1381，需要加括号。
- **antd v5 的 `message.success()` 静态方法拿不到主题 context**，
  要用 `App.useApp()`。但 `request.ts` 这种模块级代码用不了 hook，
  所以做了 `services/notify.ts` 桥接：`MessageBridge` 组件把实例注入模块级变量。
- **Modal 上要加 `forceRender`**：否则关闭时 Form 被卸载，
  而 `useForm` 的实例还在，antd 会警告「Instance created by useForm is not connected to any Form element」。

## 命令

```bash
npx tsc --noEmit   # 类型检查
npm run build       # 构建
```
