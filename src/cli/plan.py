"""交易计划管理 CLI。"""

import json
from datetime import datetime
from pathlib import Path

import typer

from src.cli.formatting import format_result
from src.common.logger import get_logger
from src.common.models import PlanReviewSnapshot, SourceMetadata, TradePlan, TradePlanStatus
from src.common.paths import get_data_dir
from src.common.snapshot_io import write_snapshot
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)


def _plans_dir() -> Path:
    path = get_data_dir("user") / "plans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _plan_path(plan_id: str) -> Path:
    return _plans_dir() / f"{plan_id}.json"


@app.command("create")
def create_plan(
    ctx: typer.Context,
    ticker: str = typer.Argument(..., help="股票代码"),
    name: str = typer.Option(..., help="计划名称"),
) -> None:
    """创建交易计划。"""
    plan_id = f"{ticker}-{generate_version(name)[:14]}"
    plan = TradePlan(
        plan_id=plan_id,
        name=name,
        ticker=ticker,
        direction="long",
        time_window="3-6m",
        research_version="unknown",
        entry_logic="placeholder",
        status=TradePlanStatus.DRAFT,
        plan_version="1",
        metadata=SourceMetadata(
            source="climbing.plan.create",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = _plan_path(plan_id)
    path.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Created plan for %s: %s -> %s", ticker, name, path)
    format_result(
        ctx,
        success=True,
        message=f"交易计划创建完成：{ticker} - {name}",
        snapshot_path=path,
        version=plan.plan_version,
        extra={"plan_id": plan_id},
    )


@app.command("list")
def list_plans(ctx: typer.Context) -> None:
    """列出所有交易计划。"""
    logger.info("Listing plans")
    plans = [p.stem for p in _plans_dir().glob("*.json")]
    format_result(
        ctx,
        success=True,
        message=f"共 {len(plans)} 条交易计划。",
        extra={"plans": plans},
    )


@app.command("check")
def check_plan(
    ctx: typer.Context,
    plan_id: str = typer.Argument(..., help="计划ID"),
) -> None:
    """检查计划偏离并生成 PlanReviewSnapshot。"""
    logger.info("Checking plan: %s", plan_id)
    plan_path = _plan_path(plan_id)
    if not plan_path.exists():
        format_result(
            ctx,
            success=False,
            message=f"计划不存在：{plan_id}",
        )
        raise typer.Exit(code=1)

    plan = TradePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    version = generate_version(f"{plan_id}-{datetime.now().isoformat()}")
    review = PlanReviewSnapshot(
        snapshot_id=f"plan-review-{plan_id}-{version}",
        version=version,
        plan_id=plan_id,
        plan_version=plan.plan_version,
        triggered_conditions=["price_placeholder"],
        deviations=["暂未检测到偏离（占位）"],
        recommendation="继续持有观察",
        metadata=SourceMetadata(
            source="climbing.plan.check",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(review, "plan_review", plan_id)
    format_result(
        ctx,
        success=True,
        message=f"计划偏离检查完成：{plan_id}",
        snapshot_path=path,
        version=version,
    )
