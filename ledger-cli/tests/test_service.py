"""业务逻辑的单元测试。运行：uv run pytest

每个函数就是一个测试用例；fixture `temp_ledger` 由 conftest.py 提供。
"""
from ledger.models import TxType
from ledger.service import LedgerService


def test_add_and_list(temp_ledger: LedgerService) -> None:
    temp_ledger.add(100, TxType.INCOME, "工资")
    temp_ledger.add(38.5, TxType.EXPENSE, "餐饮")
    assert len(temp_ledger.all()) == 2


def test_summary(temp_ledger: LedgerService) -> None:
    temp_ledger.add(100, TxType.INCOME, "工资")
    temp_ledger.add(30, TxType.EXPENSE, "餐饮")
    temp_ledger.add(20, TxType.EXPENSE, "交通")
    s = temp_ledger.summary()
    assert s["income"] == 100
    assert s["expense"] == 50
    assert s["balance"] == 50
    assert s["count"] == 3


def test_delete(temp_ledger: LedgerService) -> None:
    tx = temp_ledger.add(50, TxType.EXPENSE, "游戏")
    assert temp_ledger.delete(tx.id) is True     # 删存在的
    assert temp_ledger.delete("不存在") is False   # 删不存在的


def test_by_category(temp_ledger: LedgerService) -> None:
    temp_ledger.add(20, TxType.EXPENSE, "餐饮")
    temp_ledger.add(30, TxType.EXPENSE, "餐饮")
    temp_ledger.add(10, TxType.EXPENSE, "交通")
    cats = temp_ledger.by_category()
    assert cats["餐饮"] == 50
    assert cats["交通"] == 10
