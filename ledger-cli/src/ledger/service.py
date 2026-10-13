"""业务逻辑层：增删查、统计。

分层思想（和你的前端分层一致）：
  CLI(main) 只负责「收参数 + 输出」
  service   只负责「业务规则」
  storage   只负责「读写文件」
这样每层可单独测试、单独替换（比如以后换 SQLite，只动 storage）。
"""
from __future__ import annotations

import csv
import uuid
from collections import defaultdict
from pathlib import Path

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

    def clear(self) -> int:
        """清空全部记录，返回被清掉的条数。"""
        records = self.storage.load()
        count = len(records)
        self.storage.save([])
        return count

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

    def by_category(self, tx_type: TxType | None = None) -> dict[str, float]:
        """按分类聚合金额。

        tx_type=None 时统计全部；否则只统计指定类型（income/expense）。
        defaultdict(float)：key 不存在自动给 0.0，对标 acc[cat]=(acc[cat]||0)+amt。
        """
        totals: dict[str, float] = defaultdict(float)
        for t in self.all():
            if tx_type is None or t.type == tx_type:
                totals[t.category] += t.amount
        return dict(totals)

    def export_csv(self, path: Path) -> int:
        """把全部记录导出为 CSV 文件，返回写入条数。

        newline="" 是 csv 模块要求（避免 Windows 下多出空行）；
        encoding="utf-8-sig" 写 BOM，让 Excel 打开中文不乱码
        （对标前端导出 CSV 时手动加 \\ufeff）。
        """
        txs = self.all()
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "日期", "类型", "金额", "分类", "备注"])
            for t in txs:
                writer.writerow([
                    t.id,
                    t.created_at.isoformat(),
                    t.type.value,
                    f"{t.amount:.2f}",
                    t.category,
                    t.note,
                ])
        return len(txs)
