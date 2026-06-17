"""交易计划管理 CLI。"""

import typer

from src.common.logger import get_logger

app = typer.Typer()
logger = get_logger(__name__)


@app.command("create")
def create_plan(
    ticker: str = typer.Argument(..., help="股票代码"),
    name: str = typer.Option(..., help="计划名称"),
) -> None:
    """创建交易计划。"""
    logger.info("Creating plan for %s: %s", ticker, name)
    typer.echo(f"交易计划创建完成（占位）：{ticker} - {name}")


@app.command("list")
def list_plans() -> None:
    """列出所有交易计划。"""
    logger.info("Listing plans")
    typer.echo("交易计划列表（占位）。")


@app.command("check")
def check_plan(
    plan_id: str = typer.Argument(..., help="计划ID"),
) -> None:
    """检查计划偏离。"""
    logger.info("Checking plan: %s", plan_id)
    typer.echo(f"计划偏离检查完成（占位）：{plan_id}")
