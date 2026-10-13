"""ETL 转换层的单元测试。"""
from energy_etl.transformer import aggregate_by_park, summarize


def test_aggregate_by_park(records) -> None:
    agg = aggregate_by_park(records)
    assert set(agg["park"]) == {"园区A", "园区B"}
    a = agg[agg["park"] == "园区A"].iloc[0]
    assert a["electricity"] == 100.0
    assert a["water"] == 10.0


def test_summarize(records) -> None:
    s = summarize(records)
    assert s["total_electricity"] == 300.0
    assert s["total_water"] == 30.0
    assert s["parks"] == 2
    assert s["months"] == 1
