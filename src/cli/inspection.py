"""一键巡检与自然语言入口 CLI worker。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.cli.update import (
    _daily_review_snapshot,
    _market_snapshot,
    _portfolio_snapshot,
    _write_system_status,
)
from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import (
    DailyReviewSnapshot,
    InspectionSnapshot,
    InspectionSummary,
    MarketSnapshot,
    PortfolioSnapshot,
    RiskReminder,
    SourceMetadata,
)
from src.common.plan_io import list_plan_ids, load_plan
from src.common.snapshot_io import read_snapshot, write_snapshot
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)

INSPECTION_INTENTS = {
    "climbing",
    "收盘巡检",
    "今日巡检",
    "巡检",
    "复盘今天",
    "one-click inspection",
    "one click inspection",
}


def route_intent(intent: str) -> str:
    """将自然语言入口映射到 worker 路由。"""
    normalized = intent.strip().lower()
    if normalized in INSPECTION_INTENTS:
        return "one_click_inspection"
    raise ValueError(f"无法识别的巡检意图：{intent}")


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.01"))


def _position_value_by_ticker(portfolio: PortfolioSnapshot) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for position in portfolio.positions:
        values[position.ticker] = values.get(position.ticker, Decimal("0")) + (
            position.market_value or Decimal("0")
        )
    return values


def _soft_risk_reminders(portfolio: PortfolioSnapshot) -> list[RiskReminder]:
    """生成软性风险提醒；只提示，不阻断、不修改计划或持仓。"""
    reminders: list[RiskReminder] = []
    total_assets = portfolio.total_assets
    total_market_value = portfolio.total_market_value
    cash = portfolio.cash

    position_pct = _pct(total_market_value, total_assets)
    if total_assets > 0 and position_pct >= Decimal("90"):
        reminders.append(
            RiskReminder(
                code="full_position",
                title="仓位接近满仓",
                detail=f"当前持仓市值占总资产 {position_pct}% ，后续操作需留意现金弹性。",
                severity="warning",
                evidence=[
                    f"total_market_value={total_market_value}",
                    f"total_assets={total_assets}",
                ],
            )
        )

    cash_pct = _pct(cash, total_assets)
    if total_assets > 0 and cash_pct <= Decimal("5"):
        reminders.append(
            RiskReminder(
                code="low_cash",
                title="现金余额偏低",
                detail=f"当前现金占总资产 {cash_pct}% ，可能影响后续计划执行。",
                severity="warning",
                evidence=[f"cash={cash}", f"total_assets={total_assets}"],
            )
        )

    values_by_ticker = _position_value_by_ticker(portfolio)
    if total_assets > 0 and values_by_ticker:
        ticker, value = max(values_by_ticker.items(), key=lambda item: item[1])
        concentration_pct = _pct(value, total_assets)
        if concentration_pct >= Decimal("40"):
            reminders.append(
                RiskReminder(
                    code="concentration",
                    title="单一标的集中度偏高",
                    detail=f"{ticker} 占总资产 {concentration_pct}% ，需要关注单票波动风险。",
                    severity="warning",
                    evidence=[f"ticker={ticker}", f"market_value={value}"],
                )
            )

    for exposure in portfolio.sector_exposure:
        if exposure.value_pct >= Decimal("50"):
            reminders.append(
                RiskReminder(
                    code="sector_exposure",
                    title="行业暴露偏集中",
                    detail=f"{exposure.category} 行业暴露为 {exposure.value_pct}% 。",
                    severity="warning",
                    evidence=[f"sector={exposure.category}", f"value_pct={exposure.value_pct}"],
                )
            )
            break

    for plan_id in list_plan_ids():
        try:
            plan = load_plan(plan_id)
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to load plan %s for inspection: %s", plan_id, exc)
            continue
        if plan.status.value not in {"active", "partially_triggered"}:
            continue
        ticker_value = values_by_ticker.get(plan.ticker, Decimal("0"))
        ticker_pct = _pct(ticker_value, total_assets)
        if ticker_pct > plan.position_limit:
            reminders.append(
                RiskReminder(
                    code="plan_position_conflict",
                    title="计划仓位与真实持仓存在偏离",
                    detail=(
                        f"{plan.ticker} 当前仓位 {ticker_pct}% 高于计划上限 "
                        f"{plan.position_limit}% ，建议复核计划。"
                    ),
                    severity="critical",
                    evidence=[f"plan_id={plan.plan_id}", f"position_limit={plan.position_limit}"],
                )
            )
            break

    return reminders


def _market_status(snapshot: MarketSnapshot) -> str:
    index_note = " / ".join(f"{index.name} {index.change_pct}%" for index in snapshot.indices[:3])
    appetite = snapshot.risk_appetite or "未知"
    return f"{snapshot.trade_date.isoformat()} 市场温度 {appetite}；{index_note}"


def _portfolio_status(snapshot: PortfolioSnapshot) -> str:
    position_pct = _pct(snapshot.total_market_value, snapshot.total_assets)
    return f"{len(snapshot.positions)} 只持仓，总资产 {snapshot.total_assets}，仓位 {position_pct}%"


def _load_macro_summary() -> dict[str, Any]:
    path = settings.project_root / "web" / "public" / "macro-report.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    keys = ["report_month", "summary", "growth_label", "liquidity_label", "market_structure_label"]
    return {key: data[key] for key in keys if key in data}


def _write_inspection_web_summary(snapshot: InspectionSnapshot) -> Path:
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    path = web_public / "inspection-summary.json"
    path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote inspection summary for web -> %s", path)
    return path


def run_inspection(intent: str, mock: bool) -> tuple[InspectionSnapshot, Path]:
    """执行一键巡检，返回结构化快照与路径。"""
    route = route_intent(intent)

    market_path, market_version = _market_snapshot()
    portfolio_path, portfolio_version = _portfolio_snapshot()

    market = read_snapshot(market_path, MarketSnapshot)
    portfolio = read_snapshot(portfolio_path, PortfolioSnapshot)
    review_path, review_version = _daily_review_snapshot(market, portfolio, mock=mock)
    review = read_snapshot(review_path, DailyReviewSnapshot)

    generated_snapshots = [
        {"report_type": "market", "snapshot_path": str(market_path), "version": market_version},
        {
            "report_type": "portfolio",
            "snapshot_path": str(portfolio_path),
            "version": portfolio_version,
        },
        {
            "report_type": "daily_review",
            "snapshot_path": str(review_path),
            "version": review_version,
        },
    ]
    _write_system_status(generated_snapshots)

    summary = InspectionSummary(
        market_status=_market_status(market),
        portfolio_status=_portfolio_status(portfolio),
        plan_deviations=len(review.plan_deviations),
        expired_research=len(review.stale_research),
        stocks_needing_review=len(review.watchlist),
    )
    risk_reminders = _soft_risk_reminders(portfolio)
    version_inputs = {
        "intent": intent,
        "route": route,
        "summary": summary.model_dump(mode="json"),
        "risk_reminders": [r.model_dump(mode="json") for r in risk_reminders],
        "plan_deviations": [d.model_dump(mode="json") for d in review.plan_deviations],
        "stale_research": [r.model_dump(mode="json") for r in review.stale_research],
        "generated_snapshots": generated_snapshots,
    }
    version = generate_version(version_inputs)
    snapshot = InspectionSnapshot(
        snapshot_id=f"inspection-{version}",
        version=version,
        intent=intent,
        route=route,
        trade_date=market.trade_date,
        summary=summary,
        risk_reminders=risk_reminders,
        plan_deviations=review.plan_deviations,
        stale_research=review.stale_research,
        watchlist=review.watchlist,
        macro_summary=_load_macro_summary(),
        generated_snapshots=generated_snapshots,
        metadata=SourceMetadata(
            source="climbing.inspect",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "inspection")
    _write_inspection_web_summary(snapshot)
    return snapshot, path


@app.callback(invoke_without_command=True)
def inspect_callback(
    ctx: typer.Context,
    intent: str = typer.Option(
        "climbing",
        "--intent",
        help="自然语言入口，如 climbing / 今日巡检 / 收盘巡检 / 复盘今天。",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用）。",
        envvar="CLIMBING_MOCK_SKILL",
    ),
) -> None:
    """一键巡检：生成市场、持仓、快速复盘和软性风险提醒。"""
    try:
        snapshot, path = run_inspection(intent=intent, mock=mock)
    except ValueError as exc:
        format_result(ctx, success=False, message=str(exc))
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        logger.error("Inspection failed: %s", exc)
        format_result(ctx, success=False, message=f"巡检失败：{exc}")
        raise typer.Exit(code=1) from exc

    format_result(
        ctx,
        success=True,
        message="One-click inspection completed.",
        snapshot_path=path,
        version=snapshot.version,
        extra={
            "intent": snapshot.intent,
            "route": snapshot.route,
            "summary": snapshot.summary.model_dump(mode="json"),
            "risk_reminders": [r.model_dump(mode="json") for r in snapshot.risk_reminders],
            "plan_deviations": [d.model_dump(mode="json") for d in snapshot.plan_deviations],
            "stale_research": [r.model_dump(mode="json") for r in snapshot.stale_research],
            "watchlist": snapshot.watchlist,
            "generated_snapshots": snapshot.generated_snapshots,
        },
    )
