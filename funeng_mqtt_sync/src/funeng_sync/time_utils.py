"""时间工具 —— 对应 index.js 里dayjs 的常用调用。

dayjs 用的是本地时区；Python 的 naive datetime 配合 .timestamp() 也按本地时区计算，
因此毫秒时间戳与 dayjs().valueOf() 行为一致。

这个模块是**纯函数层**：不碰网络、不读配置、不持有状态，
所以能被单测直接覆盖（原 http_client 里的请求逻辑已随阶段二裁剪移除）。
"""
from __future__ import annotations

from datetime import datetime, timedelta


def now_millis() -> int:
    """dayjs().valueOf() —— 当前时间毫秒戳。"""
    return int(datetime.now().timestamp() * 1000)


def _start_of_day(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(d: datetime) -> datetime:
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_day_millis(d: datetime | None = None) -> int:
    """当天 0 点毫秒戳。"""
    return int(_start_of_day(d or datetime.now()).timestamp() * 1000)


def end_of_day_millis(d: datetime | None = None) -> int:
    """当天 23:59:59.999 毫秒戳 —— 对应dayjs().endOf('day')。"""
    return int(_end_of_day(d or datetime.now()).timestamp() * 1000)


def yesterday_start_millis() -> int:
    """dayjs().subtract(1, 'day').startOf('day') —— 昨天 0 点毫秒戳。

    用于 getData 的查询区间：只要"昨天 0 点 → 今天结束"，
    这样服务端返回的表里就一定含有昨天的累计流量。
    """
    return start_of_day_millis(datetime.now() - timedelta(days=1))


def parse_read_time(raw: object) -> datetime:
    """把 readTime 解析成 datetime。

    接口返回的格式有两种：``"2026-10-13 00:00:00"`` 和带 Z 的 ISO 8601，
    所以先把 Z 换成 +00:00 再交给 fromisoformat。
    """
    s = str(raw).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def is_top_of_hour(raw: object) -> bool:
    """dayjs(readTime).minute() === 0 —— 是否整点。解析失败返回 False。

    主循环只处理整点数据，所以这里是第一道过滤。
    注意用 try/except 而不是让异常上抛：单条脏数据不该中断整轮同步。
    """
    try:
        return parse_read_time(raw).minute == 0
    except Exception:
        return False


def format_read_time(raw: object) -> str:
    """dayjs(readTime).format('YYYY-MM-DD HH:mm:ss') —— 仅用于日志。"""
    try:
        return parse_read_time(raw).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(raw)