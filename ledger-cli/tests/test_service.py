"""业务逻辑的单元测试。运行：uv run pytest

每个函数就是一个测试用例；fixture `temp_ledger` 由 conftest.py 提供。
"""
import csv
from datetime import date

from ledger.models import Transaction, TxType
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


def test_clear(temp_ledger: LedgerService) -> None:
    temp_ledger.add(100, TxType.INCOME, "工资")
    temp_ledger.add(30, TxType.EXPENSE, "餐饮")
    assert len(temp_ledger.all()) == 2
    n = temp_ledger.clear()
    assert n == 2
    assert temp_ledger.all() == []


def test_by_category_with_type(temp_ledger: LedgerService) -> None:
    temp_ledger.add(100, TxType.INCOME, "工资")
    temp_ledger.add(30, TxType.EXPENSE, "餐饮")
    temp_ledger.add(20, TxType.EXPENSE, "餐饮")
    # 不传类型 = 全部
    assert temp_ledger.by_category()["餐饮"] == 50
    # 只统计收入
    assert temp_ledger.by_category(TxType.INCOME) == {"工资": 100}
    # 只统计支出
    assert temp_ledger.by_category(TxType.EXPENSE)["餐饮"] == 50


def test_export_csv(temp_ledger: LedgerService, tmp_path) -> None:
    temp_ledger.add(100, TxType.INCOME, "工资", "十月")
    temp_ledger.add(38.5, TxType.EXPENSE, "餐饮")
    out = tmp_path / "out.csv"
    n = temp_ledger.export_csv(out)
    assert n == 2
    # 读回校验：用 csv 模块解析刚导出的文件
    rows = list(csv.reader(out.read_text(encoding="utf-8-sig").splitlines()))
    assert rows[0] == ["id", "日期", "类型", "金额", "分类", "备注"]
    assert len(rows) == 3  # 表头 + 2 条数据
    assert rows[1][4] == "工资"


def test_monthly_summary(temp_ledger: LedgerService) -> None:
    # 直接构造含指定日期的记录，覆盖跨月+ 同月多笔
    temp_ledger.storage.save([
        Transaction(
            id="a", amount=100, type=TxType.INCOME,
            category="工资", created_at=date(2026, 10, 1),
        ).to_dict(),
        Transaction(
            id="b", amount=30, type=TxType.EXPENSE,
            category="餐饮", created_at=date(2026, 10, 15),
        ).to_dict(),
        Transaction(
            id="c", amount=50, type=TxType.INCOME,
            category="奖金", created_at=date(2026, 9, 20),
        ).to_dict(),
    ])
    result = temp_ledger.monthly_summary()
    assert list(result.keys()) == ["2026-09", "2026-10"]  # 月份升序
    assert result["2026-09"]["income"] == 50
    assert result["2026-10"]["income"] == 100
    assert result["2026-10"]["expense"] == 30
