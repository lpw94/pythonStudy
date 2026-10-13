"""数据模型层：四类能源 + 一条记录的结构。

对标前端：TypeScript interface + enum。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EnergyType(str, Enum):
    """四类能源。继承 str 是为了序列化/打印友好。"""

    ELECTRICITY = "electricity"  # 电量
    WATER = "water"  # 水量
    GAS = "gas"  # 天然气
    HEAT = "heat"  # 热力


# 中文标签映射，便于终端/报表输出
ENERGY_TYPE_LABELS: dict[EnergyType, str] = {
    EnergyType.ELECTRICITY: "电量",
    EnergyType.WATER: "水量",
    EnergyType.GAS: "天然气",
    EnergyType.HEAT: "热力",
}


@dataclass
class EnergyRecord:
    """一条月度能源记录（park 维度）。

    字段顺序即 Excel 列顺序；金额统一用正数，四类分开存。
    product 维度（organizationIds）可后续扩展为 organization 字段。
    """

    month: str  # 月份，如 "2026-01"
    park: str  # 园区/区域（对应 scopeType=park 的 areaIds）
    electricity: float  # 电量
    water: float  # 水量
    gas: float  # 天然气
    heat: float  # 热力
