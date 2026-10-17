"""时间工具的单元测试（纯函数，无需网络）。"""
from funeng_sync.time_utils import (end_of_day_millis, is_top_of_hour,
                                    now_millis, start_of_day_millis,
                                    yesterday_start_millis)


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
