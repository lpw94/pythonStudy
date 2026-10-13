"""pytest 夹具（fixtures）：测试前的公共准备，对标 Jest 的 beforeEach。

tmp_path 是 pytest 内置夹具，提供一个测试结束后自动清理的临时目录，
保证每个测试用独立数据文件，互不污染。
"""
from pathlib import Path

import pytest

from ledger.service import LedgerService
from ledger.storage import Storage


@pytest.fixture
def temp_ledger(tmp_path: Path) -> LedgerService:
    """返回一个用临时文件的账本服务。"""
    storage = Storage(tmp_path / "test_ledger.json")
    return LedgerService(storage)
