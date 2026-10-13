"""生成示例 Excel：四类能源月度数据（park 维度）。

运行：python scripts/make_sample.py
真实接入时删掉本脚本，改由 fetcher 拉取线上 Excel。
"""
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent


def make_sample(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "能源月度"
    # 列名需与 models.EnergyRecord 字段对应
    ws.append(["month", "park", "electricity", "water", "gas", "heat"])
    rows = [
        ["2026-01", "园区A", 1200.5, 300.2, 150.0, 80.5],
        ["2026-01", "园区B", 980.0, 250.0, 120.0, 60.0],
        ["2026-02", "园区A", 1250.0, 310.0, 160.0, 85.0],
        ["2026-02", "园区B", 1000.0, 260.0, 130.0, 62.0],
        ["2026-03", "园区A", 1300.0, 320.0, 170.0, 90.0],
        ["2026-03", "园区B", 1050.0, 270.0, 140.0, 65.0],
    ]
    for r in rows:
        ws.append(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print(f"已生成示例 {path}")


if __name__ == "__main__":
    make_sample(ROOT / "data" / "sample_energy.xlsx")
