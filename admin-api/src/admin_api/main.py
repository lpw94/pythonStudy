"""FastAPI 应用入口。

对标前端 `src/main.tsx`：创建 app、挂路由、配中间件、启动。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, menus, roles, users
from .config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="admin-web 权限路由后端 · 阶段3 Python 学习项目",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件：允许前端域名跨域访问。
# 对标 express 的 cors({ origin: [...] })。
# 放在路由注册之前，且是「中间件」——每次请求都会过一遍。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由。include_router 对标 express 的 app.use('/api/auth', authRouter)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(menus.router)
app.include_router(roles.router)


@app.get("/api/health", tags=["系统"], summary="健康检查")
def health() -> dict[str, str]:
    """健康检查：给部署平台的探活用，也可以确认服务活着。"""
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """根路径：直接指路到接口文档。"""
    return {"docs": "/docs", "message": f"{settings.app_name} is running"}
