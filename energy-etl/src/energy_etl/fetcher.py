"""取数层：用 httpx 拉取远程 Excel/数据。

脚手架默认 remote_url 为空，直接复用本地示例文件（不联网）。
真实接入时把 config.remote_url 指向你的接口，或在此替换解析逻辑。
"""
from __future__ import annotations

from pathlib import Path

import httpx

from .config import settings


def fetch_remote(url: str | None = None, dest: Path | None = None) -> Path:
    """下载远程数据到本地；无 url 时直接返回本地路径（占位）。

    Args:
        url: 远程地址；为空则用 settings.remote_url
        dest: 本地落盘路径；为空则用 settings.excel_path
    Returns:
        最终要读取的本地文件路径
    """
    url = url or settings.remote_url
    dest = dest or settings.excel_path
    if not url:
        # 脚手架占位：没有远程源，直接用本地示例
        return dest
    # httpx 比 requests 更现代；follow_redirects 处理 302
    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest
