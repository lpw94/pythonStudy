"""存储层：JSON 文件读写（对标前端的 localStorage 或一个小 db.json）。

用 pathlib.Path 处理路径，比 os.path 更 Pythonic（支持 / 链式拼路径）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Storage:
    """负责把交易列表持久化到 JSON 文件。"""

    def __init__(self, path: Path | str = "ledger.json") -> None:
        # Path | str 表示「可接受两种类型」，Union 的现代写法
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        """读取全部记录。文件不存在时返回空列表（不报错）。

        列表推导式：[x for x in 可迭代 if 条件]
        对标 JS 的 arr.map(...) 或 arr.filter(...)。
        """
        if not self.path.exists():
            return []
        # ⚠️ Windows 默认编码是 GBK，不指定 utf-8 中文会乱码
        raw = self.path.read_text(encoding="utf-8")
        records: list[dict[str, Any]] = json.loads(raw)
        return records

    def save(self, records: list[dict[str, Any]]) -> None:
        """覆盖写入全部记录。parents=True 自动建父目录。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # ensure_ascii=False 让中文原样保存，indent=2 格式化便于肉眼看
        self.path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
