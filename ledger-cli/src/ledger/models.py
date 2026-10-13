"""数据模型层：用 dataclass 描述一笔交易。

为什么用 dataclass 而不是 dict？
- 自带类型注解，IDE 能自动补全字段（对标 TS interface）
- 自动生成 __init__ / __repr__ / __eq__，少写一堆样板代码
- 想加方法直接在类里写（OOP 习惯沿用你的前端 class）
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum


class TxType(str, Enum):
    """交易类型。继承 str 是为了 JSON 序列化友好（直接存成字符串）。"""
    INCOME = "income"
    EXPENSE = "expense"


@dataclass
class Transaction:
    """一笔收支记录。

    类型注解写法：`字段名: 类型 = 默认值`
    对标 TS：`{ id: string; amount: number; type: TxType; ... }`
    """

    id: str
    amount: float          # 金额，统一存正数，正负靠 type 区分
    type: TxType           # 收入 / 支出
    category: str          # 分类，如「餐饮」「工资」
    note: str = ""         # 备注，默认空串（有默认值的字段放后面）
    created_at: date = date.today()  # 日期，默认今天

    def to_dict(self) -> dict:
        """转成可 JSON 序列化的字典。

        Enum 和 date 都不是 JSON 原生类型，必须手动转成基本类型。
        asdict 会把 dataclass 拍平成 dict，但里面仍含 Enum/date 对象。
        """
        data = asdict(self)
        data["type"] = self.type.value            # Enum -> "income" / "expense"
        data["created_at"] = self.created_at.isoformat()  # date -> "2026-10-13"
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Transaction:
        """字典反序列化，是 to_dict 的逆操作（类方法，对标 static 但能拿到 cls）。"""
        return cls(
            id=data["id"],
            amount=float(data["amount"]),
            type=TxType(data["type"]),            # 字符串 -> Enum
            category=data["category"],
            note=data.get("note", ""),            # dict.get(k, default) 防 key 缺失
            created_at=date.fromisoformat(data["created_at"]),
        )
