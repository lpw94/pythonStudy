"""应用配置：从环境变量 / .env 读取。

对标前端：`const API_BASE = import.meta.env.VITE_API_BASE`
区别：Python 这边用 pydantic-settings 读 .env，和 Vite 的 .env 机制类似，
但多了一层「带类型的字段 + 校验」，写错端口会直接启动失败而不是运行时才炸。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（src/admin_api/config.py 往上三级即 admin-api/）
ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """所有可配置项集中在这里，别的模块只读不写。"""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 基本信息 ----
    app_name: str = "admin-api"
    app_version: str = "0.1.0"
    debug: bool = True

    # ---- 数据库 ----
    # SQLite 单文件数据库，阶段3 用它最省事（不用装服务）。
    # 换成 Postgres 只需改这一行 + 装 psycopg（asyncpg）。
    database_url: str = f"sqlite:///{(ROOT / 'admin.db').as_posix()}"

    # ---- JWT ----
    # 生产环境务必用环境变量覆盖，不要把密钥写进仓库。
    # HS256 要求密钥至少 32 字节（RFC 7518 §3.2），低于会告警。
    jwt_secret: str = "dev-only-change-me-please-32bytes-min"
    jwt_algorithm: str = "HS256"
    # 访问令牌有效期（分钟）
    access_token_expire_minutes: int = 60 * 12
    # 刷新令牌有效期（天）
    refresh_token_expire_days: int = 7

    # ---- CORS ----
    # 允许的前端来源，逗号分隔。对标 express 的 cors({ origin: [...] })
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的字符串切成列表，顺手去掉空白项。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """单例：第一次调用读 .env，之后都走缓存。

    lru_cache 是标准库的缓存装饰器，对标前端的「模块单例」——
    配置文件只读一次，后续 import 直接拿实例。
    """
    return Settings()


settings = get_settings()
