"""Alembic 运行时环境：连接数据库、比对模型差异、执行迁移。

对标前端的 `prisma migrate`：
- `target_metadata` = 期望的表结构（来自 SQLAlchemy 模型）
- autogenerate    = 对比「当前数据库」和「期望结构」，把差异翻译成 ALTER/CREATE 语句

关键点：**必须 import 全部模型**，否则 metadata 是空的，
autogenerate 会认为所有表都是「多余的」，生成一堆 drop_table。
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 让 alembic 能 import 到 src/admin_api（项目用 src layout，没装成包时也能跑）
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import admin_api.models  # noqa: E402,F401  ← 关键：导入模型以注册到 Base.metadata
from admin_api.config import settings  # noqa: E402
from admin_api.database import Base  # noqa: E402

# Alembic 的 Config 对象（读 alembic.ini）
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据：所有模型都注册在这里
target_metadata = Base.metadata


def get_url() -> str:
    """数据库连接串。

    优先级：环境变量/ .env 里的 DATABASE_URL > alembic.ini 的 sqlalchemy.url。
    这样生产环境只需改 .env，不用动迁移脚本。
    """
    return settings.database_url or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 脚本，不连数据库。

    对标 `prisma migrate diff --script`——
    改表结构但没法连库时，先出一份 SQL 给人 review。
    """
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite 不支持 ALTER COLUMN，autogenerate 时会提示
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连上数据库真跑。"""
    # 如果外部注入了 connection（比如测试用内存库），直接用它——
    # 这样测试和生产的表结构来自同一份迁移脚本，不会走偏。
    # Alembic 官方推荐的 "using an existing connection" 模式。
    injected = config.attributes.get("connection")
    if injected is not None:
        context.configure(
            connection=injected,
            target_metadata=target_metadata,
            render_as_batch=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite 改列要靠 batch 模式（临时建新表再拷数据）
            render_as_batch=True,
            # 迁移里不要每次都开事务（SQLite 的 DDL 是隐式提交的）
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
