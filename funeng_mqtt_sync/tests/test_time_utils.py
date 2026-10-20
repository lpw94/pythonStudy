"""时间工具的单元测试（纯函数，无需网络）。"""
from funeng_sync.time_utils import (
    end_of_day_millis,
    format_read_time,
    is_top_of_hour,
    now_millis,
    parse_read_time,
    start_of_day_millis,
    yesterday_start_millis,
)


def test_now_millis_is_int() -> None:
    assert isinstance(now_millis(), int)


def test_start_before_end_of_day() -> None:
    assert start_of_day_millis() < end_of_day_millis()


def test_yesterday_before_today() -> None:
    assert yesterday_start_millis() < start_of_day_millis()


def test_is_top_of_hour() -> None:
    assert is_top_of_hour("2026-10-13 00:00:00") is True
    assert is_top_of_hour("2026-10-13 00:30:00") is False
    assert is_top_of_hour("2026-10-13T08:00:00Z") is True
    assert is_top_of_hour("not-a-date") is False


def test_is_top_of_hour_ignores_second_field() -> None:
    """只判断 minute，秒数不影响是否整点。

    这条是补的：原实现只看 minute，如果哪天误改成同时判断 second，
    `00:00:30` 这种数据会被误过滤掉，而测试是唯一的防线。
    """
    assert is_top_of_hour("2026-10-13 09:00:59") is True


def test_parse_read_time_accepts_both_formats() -> None:
    """接口同时存在「空格分隔」和「ISO 带 Z」两种格式，都得能解析。"""
    a = parse_read_time("2026-10-13 08:30:00")
    b = parse_read_time("2026-10-13T08:30:00Z")
    assert a.year == b.year and a.month == b.month
    assert a.hour == b.hour and a.minute == b.minute


def test_format_read_time_fallback_on_bad_input() -> None:
    """脏数据不该让日志格式化抛异常，原样返回即可。"""
    assert format_read_time("not-a-date") == "not-a-date"
