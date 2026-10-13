"""转换层：用 pandas 做清洗与聚合（ETL 的 T）。

对标前端在 JS 里手动 reduce 分组求和；pandas 一行 groupby 搞定。
"""
from __future__ import annotations

import pandas as pd

from .models import EnergyRecord


def to_dataframe(records: list[EnergyRecord]) -> pd.DataFrame:
    """把记录列表转成 DataFrame，方便后续向量化计算。"""
    # dataclass 实例的 __dict__ 即字段字典
    return pd.DataFrame([vars(r) for r in records])


def aggregate_by_park(records: list[EnergyRecord]) -> pd.DataFrame:
    """按园区（park 维度）聚合四类能源总量。

    对标 scopeType=park 维度下的 areaIds 聚合逻辑。
    """
    df = to_dataframe(records)
    agg = df.groupby("park")[["electricity", "water", "gas", "heat"]].sum().reset_index()
    return agg


def summarize(records: list[EnergyRecord]) -> dict:
    """全局总览：月份数、园区数、四类能源合计。"""
    df = to_dataframe(records)
    return {
        "months": int(df["month"].nunique()),
        "parks": int(df["park"].nunique()),
        "total_electricity": float(df["electricity"].sum()),
        "total_water": float(df["water"].sum()),
        "total_gas": float(df["gas"].sum()),
        "total_heat": float(df["heat"].sum()),
    }
