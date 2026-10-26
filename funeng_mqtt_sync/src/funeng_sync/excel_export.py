"""把取数结果导出成 Excel（.xlsx）。

用法：
    E:/workBuddy/pythonStudy/.py312/python.exe -m funeng_sync.meter_data --excel

产物落在 ``out/`` 目录下（已被 .gitignore 忽略），
因为表里含真实表号与设备编号，属于生产数据，不该进版本库。

---

## 三个实测坑，直接决定了这份 Excel 的列怎么设计

写这个模块时先把接口返回的字段逐个探了一遍，有三件事和直觉相反：

### 1. `totalFlux` 是**净值**，不是单调递增的累计量

    totalFlux == plusTotalFlux - reverseTotalFlux      # 恒等式，实测 0 处不符

所以 `totalFlux` 会**下降**——实测某台表 129 条里有 56 次下降，
因为那台表存在反向流量（`reverseTotalFlux` 在涨）。

**后果**：不能用「末值 - 首值」当成总用水量——那台表算出来是 +37.59，
但正向实际走了 +70.56、反向倒退了 +32.96，两者含义完全不同。
汇总表因此同时给「正向用量」「反向用量」「净用量」三列。

### 2. `flux` 是**瞬时流量**，不是用量

相邻两条的 `ΔtotalFlux ≈ flux × 0.25`（15 分钟 = 0.25 小时），
比例接近但不恒定——它是个流速值。

**后果**：不能把 `flux` 直接求和当用量。
明细表里的「本期用量」一律用**累计量差值**算。

### 3. 采样粒度**不统一**

4 台表是 15 分钟一采，另有 1 台是 5 分钟一采（363 条 vs 129 条）。

**后果**：横向对比各表时，不标注粒度会误读——
那条 5 分钟粒度的表条数多，不是因为它采得更久，而是因为它采得更密。
汇总表因此给出「采样间隔（分钟）」列。

---

## 三个 sheet

| Sheet | 内容 |
|-------|------|
| 汇总 | 每台表一行：区间用量、条数、粒度、时间跨度、备注 |
| 明细 | 全部读数逐条列出，含本期用量差值，可筛选 |
| 整点数据 | 只留整点读数——下一阶段 MQTT 上报的候选集 |
| 趋势 | 时间 × 各表累计流量的透视表 + 折线图 |

用整点 sheet 而不是直接过滤明细，是为了让「上报口径」在文件里
一眼可见，而不是要读者自己去筛。

## 依赖

openpyxl。**没装会给出明确报错**（而不是 ImportError 栈），
因为这个项目有一堆环境坑（.py312 / .venv / uv 三套），
报错得指得清是哪个环境缺东西。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from funeng_sync.time_utils import is_top_of_hour, parse_read_time

# 输出目录（已被 .gitignore 忽略：表里有真实表号，不进版本库）
OUT_DIR = Path(__file__).resolve().parents[2] / "out"

# 文件名前缀
FILE_PREFIX = "水表数据"

# 表头样式
HEADER_FILL = "DDEBF7"
HEADER_FONT_BOLD = True
BORDER_THIN = "BFBFBF"

# 数字格式
FMT_FLUX = "#,##0.000"
FMT_DATETIME = "yyyy-mm-dd hh:mm:ss"

# 各列宽度（按内容长度给，够用即可）
COL_WIDTHS_DETAIL = {
    "A": 14,  # 设备编号
    "B": 20,  # 读数时间
    "C": 20,  # 接收时间
    "D": 15,  # 数据延迟(分钟)
    "E": 8,  # 整点
    "F": 14,  # 瞬时流量
    "G": 16,  # 累计流量
    "H": 16,  # 正向累计
    "I": 16,  # 反向累计
    "J": 14,  # 本期净用量
    "K": 14,  # 本期正向用量
}

COL_WIDTHS_SUMMARY = {
    "A": 14,
    "B": 14,
    "C": 12,
    "D": 11,
    "E": 11,
    "F": 16,
    "G": 20,
    "H": 20,
    "I": 15,
    "J": 16,
    "K": 16,
    "L": 17,
    "M": 14,
    "N": 30,
}


class ExportError(RuntimeError):
    """导出失败（依赖缺失、路径不可写等）。"""


def _require_openpyxl() -> Any:
    """导入 openpyxl，没装时给出能指路的报错。

    这个项目有三套 Python 环境（.venv / .py312 / uv），
    光说「No module named openpyxl」用户根本不知道该往哪个环境装。
    """
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as e:
        raise ExportError(
            "缺少 openpyxl，无法导出 Excel。\n"
            "  3.12 环境（跑取数的那个）："
            " E:/workBuddy/pythonStudy/.py312/python.exe -m pip install openpyxl\n"
            "  3.13 环境（跑单测的）："
            " funeng_mqtt_sync/.venv/Scripts/python.exe -m pip install openpyxl"
        ) from e
    return openpyxl


def _num(value: Any) -> float | None:
    """把接口的值转成 float，None / 非数字返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time_key(raw: Any) -> Any:
    """给 readTime 生成可排序、可做字典键的归一化值。

    接口返回的 readTime 实测有三种形态：毫秒时间戳（int 或数字字符串）、
    ``"2026-10-13 00:00:00"``、带 Z 的 ISO 8601。
    统一成「能排序的键」后，趋势透视表才能把不同设备对齐到同一行。
    """
    if isinstance(raw, bool):
        return str(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw).strip()
    if text.isdigit():
        return int(text)
    return text


def _delay_minutes(read_raw: Any, receive_raw: Any) -> float | None:
    """数据延迟（分钟）= 接收时间 - 读数时间。

    实测 `receiveTime` 是平台**批量补传**的时间戳：同一批里几十条
    读数共用一个 receiveTime，与 readTime 相差最多 7.77 小时。
    所以这个差值反映的是「数据补传滞后」，不是单表通信延迟。
    """
    read_dt = _dt(read_raw)
    receive_dt = _dt(receive_raw)
    if read_dt is None or receive_dt is None:
        return None
    return (receive_dt - read_dt).total_seconds() / 60


def _dt(raw: Any) -> datetime | None:
    """把 readTime 解析成 datetime，失败返回 None。"""
    try:
        return parse_read_time(raw)
    except Exception:
        return None


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把一个设备的读数按时间**升序**排。

    服务端返回的是**倒序**（最新在前）——原 Node 脚本直接 slice(0, 33)
    截的是「最新的 33 条整点」。升序排是算「本期用量差值」的前提：
    差值必须是「这一条 减 上一条」，方向反了符号就全错。
    """
    decorated = []
    for index, row in enumerate(rows):
        dt = _dt(row.get("readTime"))
        # 解析失败的排到最后，但保持它们之间的原始相对顺序
        key = (dt is None, dt or datetime.min, index)
        decorated.append((key, row))
    decorated.sort(key=lambda item: item[0])
    return [row for _, row in decorated]


def _sample_interval_minutes(rows: list[dict[str, Any]]) -> int | None:
    """估计采样间隔（分钟）——取相邻时间差的中位数。

    用中位数而不是平均值：偶发的时间跳变（补传数据会让某些点密集）
    会把平均值拉偏，中位数更稳。
    """
    times = sorted(t for t in (_dt(r.get("readTime")) for r in rows) if t is not None)
    if len(times) < 2:
        return None

    gaps = []
    for a, b in zip(times, times[1:], strict=False):
        minutes = (b - a).total_seconds() / 60
        if minutes > 0:
            gaps.append(minutes)
    if not gaps:
        return None

    gaps.sort()
    mid = len(gaps) // 2
    if len(gaps) % 2:
        return int(round(gaps[mid]))
    return int(round((gaps[mid - 1] + gaps[mid]) / 2))


def _build_note(
    rows: list[dict[str, Any]],
    net_usage: float | None,
    reverse_usage: float | None,
    plus_usage: float | None,
    interval: int | None,
) -> str:
    """生成汇总表的备注列。

    备注不是装饰——它标注的是「读这张表时容易看错的地方」。
    """
    if not rows:
        return "无数据"

    notes: list[str] = []

    # 净用量为负 = 整段区间净倒退，通常是有反向流量
    if net_usage is not None and net_usage < 0:
        notes.append("净用量为负（区间内净倒退）")

    # 反向占正向的比例超过 10% 就要提醒：净用量会显著低估实际过水。
    #
    # 这里用**占比**而不是「反向 > 净」。早期版本写的是
    # `reverse_usage > net_usage`，几乎永远不成立：反向要超过净，
    # 意味着净已经被反向吃光了。而真正危险的区间恰恰是
    # 正向走了 70、反向倒回 33（占 47%）——净还有 37 看着完全正常，
    # 但单看净用量会低估将近一半的过水量。
    if (
        reverse_usage is not None
        and plus_usage is not None
        and reverse_usage > 0
        and plus_usage > 0
    ):
        ratio = reverse_usage / plus_usage
        if ratio >= 0.1:
            notes.append(f"反向流量显著（占正向流量的 {ratio:.0%}）")

    # 粒度不统一时提醒别直接比条数
    if interval is not None and interval not in (5, 15):
        notes.append(f"采样间隔 {interval} 分钟")

    return "；".join(notes) if notes else "-"


def _style_header(ws: Any, headers: list[str], row: int = 1) -> None:
    """给表头加粗、填色、居中。"""
    from openpyxl.styles import Alignment, Font, PatternFill  # noqa: PLC0415

    fill = PatternFill("solid", fgColor=HEADER_FILL)
    font = Font(bold=HEADER_FONT_BOLD)
    align = Alignment(horizontal="center", vertical="center")

    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.fill = fill
        cell.font = font
        cell.alignment = align


def _apply_widths(ws: Any, widths: dict[str, int]) -> None:
    """设置列宽。"""
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def _write_summary_sheet(wb: Any, payload: dict[str, list[dict[str, Any]]],
                         devices: list[dict[str, str]]) -> None:
    """写「汇总」sheet：每台表一行。"""
    from openpyxl.chart import BarChart, Reference  # noqa: PLC0415
    from openpyxl.styles import Font  # noqa: PLC0415

    ws = wb.create_sheet("汇总")

    headers = [
        "设备编号", "表地址", "表号", "采样条数", "整点条数",
        "采样间隔(分钟)", "起始时间", "结束时间",
        "区间净用量", "区间正向用量", "区间反向用量",
        "末次累计流量", "平均瞬时流量", "备注",
    ]
    ws.append(headers)
    _style_header(ws, headers)

    # 设备元信息（表地址 / 表号）按 deviceCode 对齐
    meta = {d.get("deviceCode", ""): d for d in devices}

    for code in payload:
        rows = _sort_rows(payload[code])
        if not rows:
            continue

        info = meta.get(code, {})
        first, last = rows[0], rows[-1]

        total_first = _num(first.get("totalFlux"))
        total_last = _num(last.get("totalFlux"))
        plus_first = _num(first.get("plusTotalFlux"))
        plus_last = _num(last.get("plusTotalFlux"))
        rev_first = _num(first.get("reverseTotalFlux"))
        rev_last = _num(last.get("reverseTotalFlux"))

        net_usage = (
            total_last - total_first
            if total_first is not None and total_last is not None
            else None
        )
        plus_usage = (
            plus_last - plus_first
            if plus_first is not None and plus_last is not None
            else None
        )
        reverse_usage = (
            rev_last - rev_first
            if rev_first is not None and rev_last is not None
            else None
        )

        top_count = sum(1 for r in rows if is_top_of_hour(r.get("readTime")))
        interval = _sample_interval_minutes(rows)

        fluxes = [f for f in (_num(r.get("flux")) for r in rows) if f is not None]
        avg_flux = sum(fluxes) / len(fluxes) if fluxes else None

        ws.append([
            code,
            info.get("fmAddress", ""),
            info.get("meterId", ""),
            len(rows),
            top_count,
            interval,
            _dt(first.get("readTime")),
            _dt(last.get("readTime")),
            net_usage,
            plus_usage,
            reverse_usage,
            total_last,
            avg_flux,
            _build_note(rows, net_usage, reverse_usage, plus_usage, interval),
        ])

    # 数字格式 + 对齐
    for r in range(2, ws.max_row + 1):
        for col in ("I", "J", "K", "L", "M"):
            ws[f"{col}{r}"].number_format = FMT_FLUX
        for col in ("G", "H"):
            ws[f"{col}{r}"].number_format = FMT_DATETIME
        for col in ("F",):
            ws[f"{col}{r}"].alignment = None
        ws[f"N{r}"].font = Font(italic=True, color="808080")

    _apply_widths(ws, COL_WIDTHS_SUMMARY)
    ws.freeze_panes = "A2"

    # 用量对比柱状图：一眼看出哪台表用水多
    if ws.max_row >= 2:
        chart = BarChart()
        chart.type = "col"
        chart.title = "各表区间正向用量对比"
        chart.y_axis.title = "用量"
        chart.height = 8
        chart.width = 18

        data_ref = Reference(
            ws, min_col=10, min_row=1, max_row=ws.max_row  # J 列 = 区间正向用量
        )
        cats_ref = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        ws.add_chart(chart, f"A{ws.max_row + 3}")


def _write_detail_sheet(wb: Any, payload: dict[str, list[dict[str, Any]]],
                         top_only: bool = False) -> None:
    """写「明细」或「整点数据」sheet。

    Args:
        top_only: True 时只写整点读数（MQTT 上报候选集）。
    """
    ws = wb.create_sheet("整点数据" if top_only else "明细")

    headers = [
        "设备编号", "读数时间", "接收时间", "数据延迟(分钟)", "整点",
        "瞬时流量", "累计流量", "正向累计", "反向累计",
        "本期净用量", "本期正向用量",
    ]
    ws.append(headers)
    _style_header(ws, headers)

    for code in payload:
        rows = _sort_rows(payload[code])
        prev_total = None
        prev_plus = None

        for row in rows:
            read_time = row.get("readTime")
            is_top = is_top_of_hour(read_time)
            if top_only and not is_top:
                # 整点 sheet 也要算差值——不能因为跳过了非整点行
                # 就把差值算错（差值是「相邻两条」，不是「相邻整点两条」）
                t = _num(row.get("totalFlux"))
                p = _num(row.get("plusTotalFlux"))
                if t is not None:
                    prev_total = t
                if p is not None:
                    prev_plus = p
                continue

            total = _num(row.get("totalFlux"))
            plus = _num(row.get("plusTotalFlux"))

            net_delta = (
                total - prev_total
                if total is not None and prev_total is not None
                else None
            )
            plus_delta = (
                plus - prev_plus
                if plus is not None and prev_plus is not None
                else None
            )

            ws.append([
                code,
                _dt(read_time),
                _dt(row.get("receiveTime")),
                _delay_minutes(read_time, row.get("receiveTime")),
                "是" if is_top else "否",
                _num(row.get("flux")),
                total,
                plus,
                _num(row.get("reverseTotalFlux")),
                net_delta,
                plus_delta,
            ])

            if total is not None:
                prev_total = total
            if plus is not None:
                prev_plus = plus

    for r in range(2, ws.max_row + 1):
        for col in ("F", "G", "H", "I", "J", "K"):
            ws[f"{col}{r}"].number_format = FMT_FLUX
        for col in ("B", "C"):
            ws[f"{col}{r}"].number_format = FMT_DATETIME
        ws[f"D{r}"].number_format = "0.0"
        ws[f"E{r}"].alignment = None

    _apply_widths(ws, COL_WIDTHS_DETAIL)
    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = f"A1:K{ws.max_row}"


def _write_trend_sheet(wb: Any, payload: dict[str, list[dict[str, Any]]]) -> None:
    """写「趋势」sheet：时间 × 各表累计流量的透视表 + 折线图。

    时间轴取所有设备时间戳的并集——各表采样点不完全重合，
    缺的格子留空，折线图上表现为断点（这比强行插值诚实）。
    """
    from openpyxl.chart import LineChart, Reference  # noqa: PLC0415

    ws = wb.create_sheet("趋势")

    codes = list(payload)
    headers = ["时间"] + codes
    ws.append(headers)
    _style_header(ws, headers)

    # 归一化时间键 -> 该时刻的累计流量 / 时间
    series: dict[str, dict[Any, tuple[float | None, datetime | None]]] = {}
    for code in codes:
        per_time: dict[Any, tuple[float | None, datetime | None]] = {}
        for row in payload[code]:
            key = _time_key(row.get("readTime"))
            per_time[key] = (_num(row.get("totalFlux")), _dt(row.get("readTime")))
        series[code] = per_time

    all_keys: set[Any] = set()
    for per_time in series.values():
        all_keys |= set(per_time)

    # 排序：数值时间戳在前按大小排，非数值的排在后面
    def _key_sort(k: Any) -> tuple[int, Any]:
        if isinstance(k, int):
            return (0, k)
        return (1, 0)

    ordered_keys = sorted(all_keys, key=_key_sort)

    for key in ordered_keys:
        row_values: list[Any] = []
        label: datetime | None = None
        for code in codes:
            value, dt = series[code].get(key, (None, None))
            row_values.append(value)
            if label is None and dt is not None:
                label = dt
        ws.append([label] + row_values)

    for r in range(2, ws.max_row + 1):
        ws[f"A{r}"].number_format = FMT_DATETIME
        for idx in range(len(codes)):
            col_letter = ws.cell(row=1, column=idx + 2).column_letter
            ws[f"{col_letter}{r}"].number_format = FMT_FLUX

    ws.column_dimensions["A"].width = 20
    for idx in range(len(codes)):
        ws.column_dimensions[ws.cell(row=1, column=idx + 2).column_letter].width = 16
    ws.freeze_panes = "B2"

    # 折线图：各表累计流量随时间变化
    if ws.max_row >= 2 and codes:
        chart = LineChart()
        chart.title = "各表累计流量趋势"
        chart.y_axis.title = "累计流量"
        chart.x_axis.title = "时间"
        chart.height = 10
        chart.width = 24

        data_ref = Reference(
            ws, min_col=2, min_row=1, max_col=len(codes) + 1, max_row=ws.max_row
        )
        cats_ref = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        ws.add_chart(chart, f"A{ws.max_row + 3}")


def export_to_excel(
    payload: dict[str, list[dict[str, Any]]],
    path: Path | str,
    devices: list[dict[str, str]] | None = None,
) -> Path:
    """把取数结果写成 xlsx。

    Args:
        payload: ``{device_code: [原始行字典, ...]}``。
            每一行是取数接口 table 里的原始 dict。
        path: 输出路径。父目录不存在会自动创建。
        devices: 设备元信息 ``[{fmAddress, meterId, deviceCode}, ...]``，
            用来在汇总表里补上表地址与表号。

    Returns:
        实际写出的文件路径。

    Raises:
        ExportError: 依赖缺失或写文件失败。
    """
    openpyxl = _require_openpyxl()
    from openpyxl.styles import Alignment  # noqa: PLC0415

    out_path = Path(path)
    if out_path.suffix.lower() != ".xlsx":
        out_path = out_path.with_suffix(".xlsx")

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ExportError(f"无法创建输出目录 {out_path.parent}：{e}") from e

    wb = openpyxl.Workbook()
    # 默认建了个叫 Sheet 的空表，删掉
    wb.remove(wb.active)

    _write_summary_sheet(wb, payload, devices or [])
    _write_detail_sheet(wb, payload, top_only=False)
    _write_detail_sheet(wb, payload, top_only=True)
    _write_trend_sheet(wb, payload)

    # 全局对齐：数值右对齐、文字左对齐
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.alignment = Alignment(horizontal="right")

    try:
        wb.save(out_path)
    except OSError as e:
        raise ExportError(f"写入 {out_path} 失败：{e}") from e

    return out_path


def default_output_path(prefix: str = FILE_PREFIX) -> Path:
    """生成默认输出路径：out/水表数据_YYYYMMDD_HHMMSS.xlsx。

    带时间戳是为了让多次导出不互相覆盖——取数是每天都在做的事，
    昨天的报表不该被今天的覆盖掉。
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUT_DIR / f"{prefix}_{stamp}.xlsx"
