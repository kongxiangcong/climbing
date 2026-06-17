"""持仓管理 CLI。"""

import typer

from src.common.logger import get_logger

app = typer.Typer()
logger = get_logger(__name__)


@app.command("summary")
def summary() -> None:
    """显示当前持仓摘要。"""
    logger.info("Showing portfolio summary")
    typer.echo("持仓摘要（占位）。")


@app.command("import")
def import_positions(
    file: str = typer.Argument(..., help="持仓 CSV 文件路径"),
) -> None:
    """从 CSV 导入持仓。"""
    logger.info("Importing positions from %s", file)
    typer.echo(f"持仓导入完成（占位）：{file}")


@app.command("transactions")
def import_transactions(
    file: str = typer.Argument(..., help="交易流水 CSV 文件路径"),
) -> None:
    """从 CSV 导入交易流水。"""
    logger.info("Importing transactions from %s", file)
    typer.echo(f"交易流水导入完成（占位）：{file}")
