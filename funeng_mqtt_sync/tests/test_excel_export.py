"""Excel 导出模块的单元测试：不联网、不加载 OCR 模型。

锁的行为（每条都对应一个实测踩过的坑）：
1. **按时间升序排** —— 服务端返回倒序，算「本期用量差值」必须升序，
   否则差值符号全反。
2. **净用量 / 正向用量 / 反向用量三个口径分开给** ——
   `totalFlux = plusTotalFlux - reverseTotalFlux`，所以 totalFlux 是净值，
   会下降；只给一个「末-首」会把反向流量的表算错。
3. **本期用量来自累计量差值，不是 flux 求和** —— flux 是瞬时流速。
4. **整点 sheet 的差值不能因为跳过非整点行而算错**。
5. **采样间隔用中位数** —— 偶发跳变不该拉偏平均值。
6. **空数据不炸** —— 少一个表就该少一行，不是整份报表失败。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from funeng_sync import excel_export
from funeng_sync.excel_export import (
    ExportError,
    default_output_path,
    export_to_excel,
)


def _row(
    read_ms: int,
    total: float,
    plus: float | None = None,
    reverse: float | None = None,
    flux: float | None = None,
    receive_ms: int | None = None,
) -> dict[str, Any]:
    """造一条原始行。

    默认 plus/reverse 满足 total = plus - reverse，
    和接口的恒等式一致。
    """
    if plus is None and reverse is None:
        plus = total
        reverse = 0.0
    return {
        "readTime": read_ms,
        "receiveTime": read_ms if receive_ms is None else receive_ms,
        "totalFlux": total,
        "plusTotalFlux": plus,
        "reverseTotalFlux": reverse,
        "flux": flux,
    }


# 2026-10-25 00:00:00 本地时间 = 1790784000000（毫秒）
T0 = 1790784000000
H = 3600_000
M15 = 15 * 60_000


@pytest.fixture
def payload() -> dict[str, list[dict[str, Any]]]:
    """两台表的数据。

    DEV-A：3 条 15 分钟间隔，净用量 +2。
    DEV-B：含反向流量（total 会下降），用来验证净值口径。
    """
    return {
        "DEV-A": [
            _row(T0 + 2 * M15, 100.0),
            _row(T0 + M15, 99.0),
            _row(T0, 98.0),
        ],
        "DEV-B": [
            _row(T0 + 2 * M15, 50.0, plus=60.0, reverse=10.0),
            _row(T0 + M15, 55.0, plus=60.0, reverse=5.0),
            _row(T0, 55.0, plus=55.0, reverse=0.0),
        ],
    }


@pytest.fixture
def devices() -> list[dict[str, str]]:
    return [
        {"fmAddress": "FA1", "meterId": "M1", "deviceCode": "DEV-A"},
        {"fmAddress": "FA2", "meterId": "M2", "deviceCode": "DEV-B"},
    ]


def _read(path: Path) -> Any:
    """把生成的 xlsx 读回来。"""
    import openpyxl  # noqa: PLC0415

    return openpyxl.load_workbook(path)


class TestExportBasics:

    def test_creates_file(self, payload, devices, tmp_path: Path) -> None:
        """文件确实生成了。"""
        out = tmp_path / "out.xlsx"
        saved = export_to_excel(payload, out, devices=devices)
        assert saved.exists()
        assert saved.stat().st_size > 0

    def test_sheet_names(self, payload, devices, tmp_path: Path) -> None:
        """四个 sheet 齐全，名字和顺序固定。"""
        out = tmp_path / "out.xlsx"
        wb = _read(export_to_excel(payload, out, devices=devices))
        assert wb.sheetnames == ["汇总", "明细", "整点数据", "趋势"]

    def test_adds_xlsx_suffix(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """没给 .xlsx 后缀时自动补上。"""
        out = tmp_path / "noext"
        saved = export_to_excel(payload, out, devices=devices)
        assert saved.suffix == ".xlsx"

    def test_creates_parent_dir(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """父目录不存在会自动建。"""
        out = tmp_path / "deep" / "nested" / "out.xlsx"
        saved = export_to_excel(payload, out, devices=devices)
        assert saved.exists()

    def test_empty_payload_still_writes(
        self, devices, tmp_path: Path
    ) -> None:
        """一台表都没数据时也要产出文件（不能直接炸）。"""
        out = tmp_path / "empty.xlsx"
        saved = export_to_excel({}, out, devices=devices)
        wb = _read(saved)
        assert wb.sheetnames == ["汇总", "明细", "整点数据", "趋势"]
        # 汇总表只有表头，没有数据行
        assert wb["汇总"].max_row == 1


class TestSummarySheet:

    def test_row_per_device(self, payload, devices, tmp_path: Path) -> None:
        """每台表一行。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        # 表头 + 2 台表
        assert ws.max_row == 3

    def test_device_meta_filled(self, payload, devices, tmp_path: Path) -> None:
        """表地址与表号从 devices 补进来。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        codes = [ws.cell(row=r, column=1).value for r in (2, 3)]
        assert codes == ["DEV-A", "DEV-B"]
        assert ws.cell(row=2, column=2).value == "FA1"
        assert ws.cell(row=2, column=3).value == "M1"

    def test_net_usage_is_ascending_diff(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """净用量 = 末条 - 首条（按时间升序）。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        # DEV-A：98 -> 100，净 +2
        assert ws.cell(row=2, column=9).value == pytest.approx(2.0)

    def test_reverse_flow_device_split(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """有反向流量的表，正向/反向/净三个口径必须分开。

        DEV-B：plus 55 -> 60（正向 +5），reverse 0 -> 10（反向 +10），
        total 55 -> 50（净 -5）。
        """
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        row = 3  # DEV-B
        assert ws.cell(row=row, column=9).value == pytest.approx(-5.0)  # 净
        assert ws.cell(row=row, column=10).value == pytest.approx(5.0)  # 正向
        assert ws.cell(row=row, column=11).value == pytest.approx(10.0)  # 反向

    def test_sample_interval_median(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """采样间隔取相邻差值的中位数。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        assert ws.cell(row=2, column=6).value == 15

    def test_top_count(self, payload, devices, tmp_path: Path) -> None:
        """整点条数统计正确。

        T0 = 00:00（整点），+15min、+30min 不是整点 → 1 条。
        """
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        assert ws.cell(row=2, column=5).value == 1

    def test_time_span(self, payload, devices, tmp_path: Path) -> None:
        """起止时间是升序后的首尾。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        assert ws.cell(row=2, column=7).value.hour == 0
        assert ws.cell(row=2, column=7).value.minute == 0
        assert ws.cell(row=2, column=8).value.minute == 30

    def test_note_flags_negative_net(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """净用量为负要写进备注——这是最容易看错的地方。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        note_b = ws.cell(row=3, column=14).value
        assert "净用量为负" in note_b

    def test_note_plain_for_normal(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """正常表备注是 '-',不啰嗦。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        assert ws.cell(row=2, column=14).value == "-"


class TestDetailSheet:

    def test_all_rows_written(self, payload, devices, tmp_path: Path) -> None:
        """明细表行数 = 表头 + 全部读数。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        assert ws.max_row == 1 + 6

    def test_sorted_ascending(self, payload, devices, tmp_path: Path) -> None:
        """按时间升序排——服务端给的是倒序。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        times = [ws.cell(row=r, column=2).value for r in range(2, 5)]
        assert times == sorted(times)

    def test_net_delta_computed(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """本期净用量 = 本条累计 - 上一条累计。

        DEV-A 升序后：98 -> 99 -> 100，差值是 +1、+1；
        第一条没有「上一条」，差值应为 None。
        """
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        assert ws.cell(row=2, column=10).value is None  # 首条无差值
        assert ws.cell(row=3, column=10).value == pytest.approx(1.0)
        assert ws.cell(row=4, column=10).value == pytest.approx(1.0)

    def test_delta_uses_cumulative_not_flux(
        self, devices, tmp_path: Path
    ) -> None:
        """本期用量来自累计量差值，不是 flux。

        构造一条 flux 很大但累计几乎不动的数据——
        如果实现偷懒用 flux 求和，结果会明显不同。
        """
        data = {
            "DEV-C": [
                _row(T0 + M15, 100.0, flux=999.0),
                _row(T0, 100.0, flux=888.0),
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        # 累计没动 → 差值 0；用 flux 求和会得到 888
        assert ws.cell(row=3, column=10).value == pytest.approx(0.0)

    def test_top_column(self, payload, devices, tmp_path: Path) -> None:
        """整点标记列是「是 / 否」。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        assert ws.cell(row=2, column=5).value == "是"
        assert ws.cell(row=3, column=5).value == "否"

    def test_autofilter_enabled(
        self, payload, devices, tmp_path: Path
    ) -> None:
        """明细表开了筛选，方便按设备筛。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        assert wb["明细"].auto_filter.ref == "A1:K{}".format(wb["明细"].max_row)

    def test_freeze_panes(self, payload, devices, tmp_path: Path) -> None:
        """冻结首行。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        assert wb["明细"].freeze_panes == "A2"


class TestTopOnlySheet:

    def test_only_top_rows(self, payload, devices, tmp_path: Path) -> None:
        """整点表只留整点行。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["整点数据"]
        # 2 台表各 1 条整点
        assert ws.max_row == 1 + 2

    def test_delta_not_broken_by_skipping(
        self, devices, tmp_path: Path
    ) -> None:
        """整点表的差值要按「相邻两条」算，不能因为跳了非整点行而错。

        构造：00:00、00:15、01:00 三个点，其中 00:00 与 01:00 是整点。
        整点表里 01:00 那条的本期净用量应该是
        「01:00 累计 - 00:15 累计」，不是「01:00 累计 - 00:00 累计」。
        """
        data = {
            "DEV-D": [
                _row(T0 + H, 120.0),
                _row(T0 + M15, 110.0),
                _row(T0, 100.0),
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["整点数据"]
        # 表头 + 00:00 + 01:00
        assert ws.max_row == 3
        # 00:00 那条：无前序，差值 None
        assert ws.cell(row=2, column=10).value is None
        # 01:00 那条：120 - 110 = 10（不是 120 - 100 = 20）
        assert ws.cell(row=3, column=10).value == pytest.approx(10.0)


class TestTrendSheet:

    def test_pivot_shape(self, payload, devices, tmp_path: Path) -> None:
        """趋势表是 时间 × 各表 的透视表。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        ws = wb["趋势"]
        assert [ws.cell(row=1, column=c).value for c in (1, 2, 3)] == [
            "时间",
            "DEV-A",
            "DEV-B",
        ]

    def test_union_of_timestamps(
        self, devices, tmp_path: Path
    ) -> None:
        """时间轴是各设备时间戳的并集。"""
        data = {
            "DEV-A": [_row(T0, 1.0)],
            "DEV-B": [_row(T0 + H, 2.0)],
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["趋势"]
        # 表头 + 2 个时间点
        assert ws.max_row == 3

    def test_missing_cells_blank(
        self, devices, tmp_path: Path
    ) -> None:
        """某设备在某个时刻没数据 → 留空，不插值。"""
        data = {
            "DEV-A": [_row(T0, 1.0)],
            "DEV-B": [_row(T0 + H, 2.0)],
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["趋势"]
        # 第 2 行是 T0：DEV-B 没数据 → 空
        assert ws.cell(row=2, column=3).value is None
        # 第 3 行是 T0+H：DEV-A 没数据 → 空
        assert ws.cell(row=3, column=2).value is None

    def test_chart_added(self, payload, devices, tmp_path: Path) -> None:
        """趋势表带折线图。"""
        wb = _read(export_to_excel(payload, tmp_path / "o.xlsx", devices=devices))
        assert len(wb["趋势"]._charts) >= 1


class TestHelpers:

    def test_time_key_normalizes(self) -> None:
        """时间键归一化：数字与数字字符串归到同一个键。"""
        assert excel_export._time_key(1790784000000) == 1790784000000
        assert excel_export._time_key("1790784000000") == 1790784000000

    def test_time_key_keeps_text(self) -> None:
        """非数字的时间字符串原样保留（不能被误转成 0）。"""
        assert excel_export._time_key("2026-10-25 00:00:00") == "2026-10-25 00:00:00"

    def test_num_handles_none_and_bad(self) -> None:
        """None / 非数字 → None，不抛异常。"""
        assert excel_export._num(None) is None
        assert excel_export._num("abc") is None
        assert excel_export._num("1.5") == pytest.approx(1.5)

    def test_num_rejects_bool(self) -> None:
        """bool 是 int 的子类，但 True 不是流量。"""
        assert excel_export._num(True) is None

    def test_default_output_path_under_out(self) -> None:
        """默认输出落在 out/ 下（已被 gitignore 忽略）。"""
        path = default_output_path()
        assert path.parent.name == "out"
        assert path.suffix == ".xlsx"

    def test_default_output_path_has_timestamp(self) -> None:
        """文件名带时间戳，多次导出不互相覆盖。"""
        path = default_output_path()
        assert path.stem.count("_") >= 1
        assert len(path.stem.split("_")[-1]) == 6  # HHMMSS

    def test_export_error_type(self) -> None:
        """ExportError 是 RuntimeError，调用方能统一捕获。"""
        assert issubclass(ExportError, RuntimeError)


class TestDelayColumn:
    """数据延迟列：receiveTime - readTime。"""

    def test_delay_computed(self, devices, tmp_path: Path) -> None:
        """延迟 = 接收时间 - 读数时间（分钟）。"""
        data = {
            "DEV-E": [
                _row(T0, 100.0, receive_ms=T0 + 30 * 60_000),  # 晚 30 分钟
                _row(T0 - M15, 99.0, receive_ms=T0 - M15),  # 无延迟
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        # 升序后：第一条无延迟，第二条晚 30 分钟
        assert ws.cell(row=2, column=4).value == pytest.approx(0.0)
        assert ws.cell(row=3, column=4).value == pytest.approx(30.0)

    def test_delay_none_when_missing(self, devices, tmp_path: Path) -> None:
        """receiveTime 缺失时留空，不报错。"""
        row = _row(T0, 100.0)
        row.pop("receiveTime")
        data = {"DEV-F": [row]}
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["明细"]
        assert ws.cell(row=2, column=4).value is None


class TestReverseRatioNote:
    """反向流量占比的备注判定。

    这条是真实 bug 的回归测试：早期实现写成
    `reverse_usage > net_usage`，而反向要超过净意味着净已被吃光，
    条件几乎永远不成立——正好漏掉最该提示的场景
    （正向 70 / 反向 33，净还有 37 看着正常，实际少算了近一半）。
    """

    def test_flags_reverse_when_net_still_positive(
        self, devices, tmp_path: Path
    ) -> None:
        """净用量为正但反向占正向 47% → 必须提示。"""
        data = {
            "DEV-G": [
                _row(T0 + M15, 137.59, plus=170.56, reverse=32.96),
                _row(T0, 100.0, plus=100.0, reverse=0.0),
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        note = ws.cell(row=2, column=14).value
        assert "反向流量显著" in note

    def test_no_flag_when_reverse_negligible(
        self, devices, tmp_path: Path
    ) -> None:
        """反向占比极低 → 不提示。

        正向走了 100、反向只有 0.1（占比 0.1%），属于正常噪声。
        """
        data = {
            "DEV-H": [
                _row(T0 + M15, 199.9, plus=200.0, reverse=0.1),
                _row(T0, 100.0, plus=100.0, reverse=0.0),
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        assert ws.cell(row=2, column=14).value == "-"

    def test_negative_net_flagged(
        self, devices, tmp_path: Path
    ) -> None:
        """净用量为负 → 提示净倒退。"""
        data = {
            "DEV-I": [
                _row(T0 + M15, 90.0, plus=100.0, reverse=10.0),
                _row(T0, 100.0, plus=100.0, reverse=0.0),
            ]
        }
        wb = _read(export_to_excel(data, tmp_path / "o.xlsx", devices=devices))
        ws = wb["汇总"]
        note = ws.cell(row=2, column=14).value
        assert "净用量为负" in note
