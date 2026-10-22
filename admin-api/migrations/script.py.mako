"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
# revision 标识：当前版本的哈希，Revises 指向上一版
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """向前：应用这次变更。"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """向后：撤销这次变更。

    写回滚很重要——线上出问题时，能退回去比能修好更值钱。
    """
    ${downgrades if downgrades else "pass"}
