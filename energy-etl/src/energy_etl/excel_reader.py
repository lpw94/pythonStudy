"""读取层：用 pandas 读取四类能源 Excel。

pandas.read_excel 默认用 openpyxl 引擎解析 .xlsx，第一行作列名。
对标前端用 xlsx / exceljs 解析表格。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import EnergyRecord


def read_excel(path: Path) -> list[EnergyRecord]:
    """读取 Excel 第一张表，返回 EnergyRecord 列表。

    Args:
        path: Excel 文件路径（.xlsx）
    Returns:
        解析后的能源记录列表
    Raises:
        FileNotFoundError: 文件不存在时
    """
    # pandas 自动把首行当列名；列名需与 models.EnergyRecord 字段对应
    df = pd.read_excel(path, sheet_name=0)
    records: list[EnergyRecord] = []
    for _, row in df.iterrows():
        records.append(
            EnergyRecord(
                month=str(row["month"]),
                park=str(row["park"]),
                electricity=float(row["electricity"]),
                water=float(row["water"]),
                gas=float(row["gas"]),
                heat=float(row["heat"]),
            )
        )
    return records
