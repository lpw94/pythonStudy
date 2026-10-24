"""时间工具的单元测试（纯函数，无需网络）。"""
from datetime import datetime

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


class TestParseReadTimeMillis:
    """毫秒时间戳格式。

    这是**实测踩出来的坑**：取数接口的 readTime 实际返回的是
    毫秒时间戳（``1792800000000``），不是日期字符串。

    原 Node 脚本写的是 ``dayjs(readTime).minute() === 0``，
    dayjs 接受数字毫秒；而 Python 侧若只按 ISO 字符串解析，
    会走到 except 返回 False —— 整点过滤全军覆没且不报错。

    ⚠️ 断言里不写死「几点几分」：毫秒时间戳转本地时间依赖机器时区，
    换台机器（比如 UTC+8 的开发机跑到 UTC+5:30 的机器）就会红。
    统一用 ``datetime.fromtimestamp`` 现场算期望值。
    """

    def test_int_millis(self) -> None:
        """int 类型的毫秒时间戳。"""
        dt = parse_read_time(1792800000000)
        expected = datetime.fromtimestamp(1792800000000 / 1000)
        assert dt == expected

    def test_numeric_string_millis(self) -> None:
        """字符串形态的毫秒时间戳（接口有时会返回字符串）。"""
        assert parse_read_time("1792800000000") == parse_read_time(1792800000000)

    def test_millis_and_iso_agree(self) -> None:
        """同一个时刻的两种表示必须解析成同一时间。"""
        dt = parse_read_time(1792800000000)
        assert dt == datetime.fromtimestamp(1792800000000 / 1000)


class TestIsTopOfHourWithMillis:
    """整点判断在毫秒时间戳上必须有效。

    构造方式：对当前时间的整点毫秒戳断言 True，
    加 15 分钟断言 False——不依赖具体日期与时区。
    """

    def _top_of_hour_millis(self) -> int:
        """当前这个整点的毫秒时间戳。"""
        now = datetime.now()
        return int(
            now.replace(hour=now.hour, minute=0, second=0, microsecond=0).timestamp()
            * 1000
        )

    def test_millis_on_the_hour(self) -> None:
        assert is_top_of_hour(self._top_of_hour_millis()) is True

    def test_millis_off_the_hour(self) -> None:
        # 加 15 分钟 —— 与实测的数据粒度一致
        assert is_top_of_hour(self._top_of_hour_millis() + 15 * 60 * 1000) is False

    def test_millis_midnight(self) -> None:
        """当天 0 点的毫秒时间戳也算整点。"""
        now = datetime.now()
        midnight = int(
            now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
        )
        assert is_top_of_hour(midnight) is True


def test_format_read_time_fallback_on_bad_input() -> None:
    """脏数据不该让日志格式化抛异常，原样返回即可。"""
    assert format_read_time("not-a-date") == "not-a-date"


def test_format_read_time_formats_millis() -> None:
    """毫秒时间戳也要格式化成可读时间，而不是原样打印数字。"""
    ts = 1792800000000
    expected = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
    assert format_read_time(ts) == expected
