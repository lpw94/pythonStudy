"""业务逻辑层：增删查、统计。

分层思想（和你的前端分层一致）：
  CLI(main) 只负责「收参数 + 输出」
  service   只负责「业务规则」
  storage   只负责「读写文件」
这样每层可单独测试、单独替换（比如以后换 SQLite，只动 storage）。
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from .models import Transaction, TxType
from .storage import Storage


class LedgerService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    # ---------------- 写操作 ----------------
    def add(
        self,
        amount: float,
        type: TxType,
        category: str,
        note: str = "",
    ) -> Transaction:
        """新增一笔交易，返回创建的对象。"""
        records = self.storage.load()
        tx = Transaction(
            id=uuid.uuid4().hex[:8],   # 取 uuid 前 8 位当简短唯一 id
            amount=round(amount, 2),   # 金额四舍五入到分
            type=type,
            category=category,
            note=note,
        )
        records.append(tx.to_dict())
        self.storage.save(records)
        return tx

    def delete(self, tx_id: str) -> bool:
        """删除指定 id 的记录，返回是否真的删掉了。"""
        records = self.storage.load()
        # 列表推导过滤掉目标 id；Python 没有 arr.filter，用推导式
        kept = [r for r in records if r["id"] != tx_id]
        if len(kept) == len(records):
            return False  # 列表长度没变 = 没删掉任何一条 = id 不存在
        self.storage.save(kept)
        return True

    def all(self) -> list[Transaction]:
        """返回全部记录（已反序列化成 Transaction 对象）。"""
        return [Transaction.from_dict(r) for r in self.storage.load()]

    # ---------------- 读 / 统计 ----------------
    def summary(self) -> dict[str, float]:
        """汇总：收入、支出、结余、笔数。

        生成器表达式 sum(x for x in ... if ...) 是惰性求值，对标 arr.reduce。
        """
        txs = self.all()
        income = sum(t.amount for t in txs if t.type == TxType.INCOME)
        expense = sum(t.amount for t in txs if t.type == TxType.EXPENSE)
        # len() 取列表长度，对标 JS 的 arr.length
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "count": len(txs),
        }

    def by_category(self) -> dict[str, float]:
        """按分类聚合支出。

        defaultdict(float) = 「不存在的 key 自动给 0.0」
        对标前端手动 `acc[cat] = (acc[cat]||0)+amt`。
        """
        totals: dict[str, float] = defaultdict(float)
        for t in self.all():
            if t.type == TxType.EXPENSE:
                totals[t.category] += t.amount
        return dict(totals)
