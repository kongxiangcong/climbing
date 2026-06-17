"""分析 CLI。"""

import typer

from src.common.logger import get_logger

app = typer.Typer()
logger = get_logger(__name__)


@app.command("stock")
def analyze_stock(
    ticker: str = typer.Argument(..., help="股票代码，如 000725.SZ"),
) -> None:
    """生成个股全景分析报告。"""
    logger.info("Analyzing stock: %s", ticker)
    # TODO: 接入实际分析流程
    typer.echo(f"个股分析报告生成完成（占位）：{ticker}")


@app.command("portfolio")
def analyze_portfolio() -> None:
    """生成持仓组合分析报告。"""
    logger.info("Analyzing portfolio")
    typer.echo("组合分析报告生成完成（占位）。")


@app.command("macro")
def analyze_macro() -> None:
    """生成市场与宏观月报。"""
    logger.info("Analyzing macro")
    typer.echo("宏观月报生成完成（占位）。")
