"""CLI 入口：用 Typer 暴露 run / serve 两个命令。

对标前端用 npm script 起定时任务；这里用命令行直接控制。
"""
from __future__ import annotations

from pathlib import Path

import typer

from .pipeline import run_pipeline
from .scheduler import start as start_scheduler

app = typer.Typer(help="阶段2 能源数据导入 ETL（对标 hourlyData.js / yearData.js）")


@app.command()
def run(
    path: Path | None = typer.Option(None, "--path", "-p", help="Excel 路径，默认用配置"),
) -> None:
    """单次运行：读取 Excel → 聚合 → 输出。"""
    run_pipeline(path)


@app.command()
def serve() -> None:
    """持续调度：按 morning/afternoon 配置定时运行。"""
    start_scheduler()


def cli() -> None:
    """控制台脚本入口（pyproject 的 [project.scripts] 指向这里）。"""
    app()


if __name__ == "__main__":
    cli()
