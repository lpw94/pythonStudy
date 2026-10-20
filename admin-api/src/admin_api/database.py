"""数据库层：引擎、会话、Base、依赖注入。

对标前端：
- `engine`       ≈ 数据库连接池配置
- `SessionLocal` ≈ 一个连接（对标 Prisma 的 `$transaction` / 一次 db.tx()）
- `get_db`       ≈ 依赖注入，FastAPI 在请求结束时自动关闭会话
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# connect_args 只对 SQLite 生效：让 SQLAlchemy 在多线程下复用同一个连接，
# 否则 SQLite 的 "check_same_thread" 限制会直接抛错。
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    echo=False,
)

# sessionmaker 是「会话工厂」：每次调用 SessionLocal() 拿到一个新会话
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。

    DeclarativeBase 是 SQLAlchemy 2.0 的新写法（老版本是 declarative_base() 函数），
    好处是 IDE 能识别类型，且和 2.0 的 `select()` 风格查询配套。

    models.py 里的所有表都注册到这个 Base 的 metadata 上，
    `Base.metadata.create_all()` 才会建出全部表——两边必须用同一个 Base。
    """


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话。

    `yield` 之后 FastAPI 会在响应发出后执行后面的代码（这里是 close），
    这就是「请求级资源自动清理」——对标 express 里手动 try/finally 关连接。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
