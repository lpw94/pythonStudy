"""CLI 入口：用 Typer 把 LedgerService 暴露成命令行工具。

对标 commander.js：每个 @app.command() 装饰的函数 = 一条子命令。
Typer 自动根据类型注解生成参数解析、--help、甚至枚举的选项。
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .models import TxType
from .service import LedgerService
from .storage import Storage

# 创建 Typer 应用；help 会出现在 `ledger --help`
app = typer.Typer(help="个人记账 CLI（阶段1 Python 学习项目）")
console = Console()

# 数据文件默认存在「当前工作目录」下的 ledger.json（已被 .gitignore 忽略）
# 运行时所在目录即数据目录，方便练习时查看和清理
_default_storage = Storage(Path("ledger.json"))
service = LedgerService(_default_storage)


@app.command()
def add(
    amount: float = typer.Argument(..., help="金额，正数，如 38.5"),
    category: str = typer.Argument(..., help="分类，如 餐饮 / 工资"),
    type: TxType = typer.Option(TxType.EXPENSE, "--type", "-t", help="income 或 expense"),
    note: str = typer.Option("", "--note", "-n", help="备注"),
) -> None:
    """新增一笔收支。

    示例: ledger add 38.5 餐饮 -t expense -n 午饭
    """
    tx = service.add(amount, type, category, note)
    # f-string：对标 JS 模板字符串 `已记录 #${tx.id}`
    console.print(f"[green]已记录[/green] #{tx.id} {tx.type.value} {tx.amount} · {tx.category}")


@app.command("list")
def list_records() -> None:
    """列出全部记录。"""
    txs = service.all()
    if not txs:
        console.print("[yellow]还没有记录，先 add 一笔吧[/yellow]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in ["ID", "日期", "类型", "金额", "分类", "备注"]:
        table.add_column(col)
    for t in txs:
        # :.2f 控制小数位（对标 JS 的 toFixed(2)）
        table.add_row(
            t.id,
            t.created_at.isoformat(),
            t.type.value,
            f"{t.amount:.2f}",
            t.category,
            t.note,
        )
    console.print(table)


@app.command("rm")
def remove(tx_id: str = typer.Argument(..., help="要删除的记录 ID")) -> None:
    """删除一条记录。"""
    if service.delete(tx_id):
        console.print(f"[red]已删除[/red] {tx_id}")
    else:
        console.print(f"[red]未找到 ID {tx_id}[/red]")


@app.command()
def summary() -> None:
    """查看收入 / 支出 / 结余 / 笔数汇总。"""
    s = service.summary()
    console.print(
        f"收入 {s['income']:.2f} | 支出 {s['expense']:.2f} | "
        f"结余 [bold]{s['balance']:.2f}[/bold] | 共 {s['count']} 笔"
    )


@app.command()
def report(
    type: TxType | None = typer.Option(
        None, "--type", "-t", help="income / expense；不填则默认按支出统计"
    ),
) -> None:
    """按分类统计金额，从高到低排序。可用 -t 按类型过滤。"""
    # 不传 -t 时保持原默认行为：只统计支出
    tx_type = type if type is not None else TxType.EXPENSE
    data = service.by_category(tx_type)
    if not data:
        console.print("[yellow]暂无记录[/yellow]")
        return
    label = type.value if type else "支出"
    table = Table(show_header=True, header_style="bold")
    table.add_column("分类")
    table.add_column(label)
    # sorted(..., key=..., reverse=True)：按金额降序；lambda kv: kv[1] 取 value
    for cat, amt in sorted(data.items(), key=lambda kv: kv[1], reverse=True):
        table.add_row(cat, f"{amt:.2f}")
    console.print(table)


@app.command()
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认直接清空"),
) -> None:
    """清空账本全部记录（不可恢复）。"""
    if not yes and not typer.confirm("确定要清空全部记录吗？此操作不可恢复"):
        console.print("[yellow]已取消[/yellow]")
        raise typer.Exit()
    n = service.clear()
    console.print(f"[red]已清空[/red] {n} 条记录")


@app.command()
def export(
    path: Path = typer.Option(
        Path("transactions.csv"), "--output", "-o", help="导出文件路径（默认 transactions.csv）"
    ),
) -> None:
    """导出全部记录为 CSV 文件（Excel 可直接打开）。"""
    n = service.export_csv(path)
    console.print(f"[green]已导出[/green] {n} 条记录 → {path}")


@app.command()
def monthly() -> None:
    """按月汇总收入 / 支出 / 结余，按月份升序。"""
    data = service.monthly_summary()
    if not data:
        console.print("[yellow]还没有记录[/yellow]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in ["月份", "收入", "支出", "结余"]:
        table.add_column(col)
    for month, vals in data.items():
        income = vals["income"]
        expense = vals["expense"]
        # 结余 = 收入 - 支出；:.2f 对标 toFixed(2)
        table.add_row(month, f"{income:.2f}", f"{expense:.2f}", f"{income - expense:.2f}")
    console.print(table)


def cli() -> None:
    """控制台脚本入口（pyproject 的 [project.scripts] 指向这里）。"""
    app()


if __name__ == "__main__":
    cli()
