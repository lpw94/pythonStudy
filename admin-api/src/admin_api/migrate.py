"""把 Alembic 包成一行可调用的函数。

为什么需要这个：
Alembic 正常是命令行工具（`alembic upgrade head`），
但有些场景必须在 Python 里触发：
- 种子脚本建表前先跑迁移
- 测试 fixture 里准备数据库
- 部署脚本里希望「建表 + 灌数据」一步到位

对标前端：把 `npx prisma migrate deploy` 包成一个 npm script，
业务代码只管调，不用关心底层命令怎么拼参数。
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

# admin-api/ 目录（migrations/ 和 alembic.ini 都在这下面）
ROOT = Path(__file__).resolve().parents[2]


def get_config() -> Config:
    """构造 Alembic 配置对象。

    注意 `config.set_main_option` 的值不能含 `%`，
    Windows 路径里的 `%` 会被当成格式占位符——这里做了转义。
    """
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


def upgrade_to_head() -> None:
    """把数据库升级到最新版本。

    已经是最新时是空操作（no-op），可以放心重复调用。
    """
    command.upgrade(get_config(), "head")


def upgrade_to_head_with(engine: Engine) -> None:
    """用给定的 engine 升级到最新版本。

    测试用这个：内存 SQLite 的 engine 传进来，
    表结构由迁移脚本创建，和生产走同一套逻辑。

    Alembic 的 configure() 要的是 Connection 不是 Engine，
    所以这里自己 connect 并保证关闭。
    """
    cfg = get_config()
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def downgrade_to_base_with(engine: Engine) -> None:
    """用给定的 engine 回滚到初始状态。

    测试清理用这个而不是 `Base.metadata.drop_all()`——
    drop_all 不会碰 alembic_version 表，版本号还留在那儿，
    下一次 upgrade 就会以为「已经是最新了」而跳过建表。

    还有一个顺序问题：自引用的 menus.parent_id 有外键，
    直接 drop_all 可能触发 FOREIGN KEY constraint failed。
    按迁移的逆序回滚就没这个问题。
    """
    cfg = get_config()
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "base")


def current_revision() -> str | None:
    """当前数据库版本号，None 表示还没打过任何迁移。"""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from .config import settings

    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
