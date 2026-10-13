"""编排层（ETL 的 orchestration）：把 取数→读→聚合→输出 串起来。

真实场景里「输出」应改为写数据库 / 推接口；脚手架先打印结果。
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .config import settings
from .excel_reader import read_excel
from .fetcher import fetch_remote
from .transformer import aggregate_by_park, summarize

console = Console()


def run_pipeline(excel_path: Path | None = None) -> dict:
    """执行一次完整的能源导入流程。

    Args:
        excel_path: 显式指定 Excel 路径；为空则用 settings.excel_path
    Returns:
        全局汇总字典（便于上层断言/落库）
    """
    path = excel_path or settings.excel_path
    # 1) 取数（无远程时返回本地文件）
    fetch_remote(dest=path)
    # 2) 读取 Excel
    records = read_excel(path)
    # 3) 聚合
    agg = aggregate_by_park(records)
    summary = summarize(records)
    # 4) 输出（真实场景此处写库 / 调接口）
    console.print("[bold]各园区能源汇总[/bold]")
    console.print(agg.to_string(index=False))
    console.print(f"[bold]总览[/bold] {summary}")
    return summary
