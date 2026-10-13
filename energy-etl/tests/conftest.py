"""pytest 夹具：用 openpyxl 在临时目录造一个最小 Excel，避免依赖 data/ 下的文件。"""
from pathlib import Path

import openpyxl
import pytest

from energy_etl.excel_reader import read_excel


@pytest.fixture
def sample_excel(tmp_path: Path) -> Path:
    p = tmp_path / "t.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["month", "park", "electricity", "water", "gas", "heat"])
    ws.append(["2026-01", "园区A", 100.0, 10.0, 5.0, 2.0])
    ws.append(["2026-01", "园区B", 200.0, 20.0, 8.0, 3.0])
    wb.save(p)
    return p


@pytest.fixture
def records(sample_excel):
    return read_excel(sample_excel)
