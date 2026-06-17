"""数据更新 CLI。"""

import typer

from src.common.config import settings
from src.common.logger import get_logger

app = typer.Typer()
logger = get_logger(__name__)


@app.command("daily")
def daily_update() -> None:
    """收盘后一键更新：价格、公告、持仓摘要、计划偏离检查。"""
    tasks = settings.get("update_schedule.daily.tasks", [])
    logger.info("Starting daily update: %s", tasks)
    for task in tasks:
        logger.info("Executing task: %s", task)
        # TODO: 接入实际任务编排
    typer.echo("Daily update completed (placeholder).")


@app.command("monthly")
def monthly_update() -> None:
    """月更任务：宏观报告、市场温度。"""
    tasks = settings.get("update_schedule.monthly.tasks", [])
    logger.info("Starting monthly update: %s", tasks)
    for task in tasks:
        logger.info("Executing task: %s", task)
        # TODO: 接入实际任务编排
    typer.echo("Monthly update completed (placeholder).")
