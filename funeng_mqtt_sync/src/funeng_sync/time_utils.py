"""时间工具 —— 对应 index.js 里 dayjs 的常用调用。

dayjs 用的是本地时区；Python 的 naive datetime 配合 .timestamp() 也按本地时区计算，
因此毫秒时间戳与 dayjs().valueOf() 行为一致。
"""
from datetime import datetime, timedelta


def now_millis() -> int:
    """dayjs().valueOf() —— 当前时间毫秒戳。"""
    return int(datetime.now().timestamp() * 1000)


def _start_of_day(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(d: datetime) -> datetime:
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_day_millis(d: datetime | None = None) -> int:
    return int(_start_of_day(d or datetime.now()).timestamp() * 1000)


def end_of_day_millis(d: datetime | None = None) -> int:
    return int(_end_of_day(d or datetime.now()).timestamp() * 1000)


def yesterday_start_millis() -> int:
    """dayjs().subtract(1, 'day').startOf('day') —— 昨天 0 点毫秒戳。"""
    return start_of_day_millis(datetime.now() - timedelta(days=1))


def parse_read_time(raw) -> datetime:
    """把 readTime（如 "2026-10-13 00:00:00" 或带 Z 的 ISO）解析成 datetime。"""
    s = str(raw).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def is_top_of_hour(raw) -> bool:
    """dayjs(readTime).minute() === 0 —— 是否整点。解析失败返回 False。"""
    try:
        return parse_read_time(raw).minute == 0
    except Exception:
        return False


def format_read_time(raw) -> str:
    """dayjs(readTime).format("YYYY-MM-DD HH:mm:ss") —— 仅用于日志。"""
    try:
        return parse_read_time(raw).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(raw)
