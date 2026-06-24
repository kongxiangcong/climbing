"""交易计划管理 CLI。"""

import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import typer

from src.analysis.plan_deviation import PlanDeviationScorer
from src.analysis.plan_state_machine import PlanStateMachine, status_display_name
from src.cli.formatting import format_result
from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import (
    MarketSnapshot,
    PlanReviewSnapshot,
    PortfolioSnapshot,
    ResearchSnapshot,
    SourceMetadata,
    TradeBatch,
    TradePlan,
    TradePlanStatus,
)
from src.common.paths import get_data_dir
from src.common.plan_io import (
    build_plan_id,
    link_transaction_to_plan,
    list_plan_ids,
    load_plan,
    plan_path,
    save_plan,
    write_plans_web_summary,
)
from src.common.skill_runner import run_skill
from src.common.snapshot_io import latest_snapshot_path, read_snapshot, write_snapshot
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)


def _load_fixture(name: str) -> dict[str, Any]:
    """加载测试 fixture；缺失时返回空字典。"""
    path = settings.project_root / "tests" / "fixtures" / name
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


def _load_json_file(path: Path | None) -> Any:
    """加载外部 JSON 文件；缺失或解析失败时返回 None。"""
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _load_latest_research(ticker: str) -> ResearchSnapshot | None:
    path = latest_snapshot_path("equity", ticker)
    if path is None:
        return None
    return read_snapshot(path, ResearchSnapshot)


def _load_latest_market() -> MarketSnapshot | None:
    path = latest_snapshot_path("market")
    if path is None:
        return None
    return read_snapshot(path, MarketSnapshot)


def _load_latest_portfolio() -> PortfolioSnapshot | None:
    path = latest_snapshot_path("portfolio")
    if path is None:
        return None
    return read_snapshot(path, PortfolioSnapshot)


def _load_context(ticker: str, research_version: str | None = None) -> dict[str, Any]:
    """构造 trade-plan skill 所需的上下文。"""
    context: dict[str, Any] = {"ticker": ticker}

    research = _load_latest_research(ticker)
    if research is not None:
        context["research_snapshot"] = research.model_dump(mode="json")
        if research_version is None:
            research_version = research.version
    else:
        context["research_snapshot"] = {"ticker": ticker}

    market = _load_latest_market()
    if market is not None:
        context["market_snapshot"] = market.model_dump(mode="json")

    portfolio = _load_latest_portfolio()
    if portfolio is not None:
        context["portfolio_snapshot"] = portfolio.model_dump(mode="json")

    context["research_version"] = research_version or "unknown"
    return context


def _run_mock_skill(ticker: str, context: dict[str, Any]) -> dict[str, Any]:
    """离线 mock：从 fixture 读取并根据 context 做最小适配。"""
    draft = _load_fixture("trade_plan_draft.json")
    draft["name"] = draft.get("name", f"{ticker} 交易计划")
    draft["research_version"] = context.get("research_version", "unknown")
    return draft


def _run_trade_plan_skill(
    ticker: str,
    context: dict[str, Any],
    mock: bool,
) -> dict[str, Any] | None:
    """调用 trade-plan skill 或 mock 生成草案。"""
    if mock:
        return _run_mock_skill(ticker, context)

    if shutil.which("kimi") is None:
        logger.warning("Kimi CLI not found, falling back to mock mode")
        return _run_mock_skill(ticker, context)

    result = run_skill(
        prompt=f"请为 {ticker} 生成交易计划草案",
        skill_name="trade-plan",
        context=context,
        timeout=120,
    )
    if not result.get("success"):
        logger.error("Trade-plan skill failed: %s", result.get("stderr", ""))
        return None

    parsed = result.get("parsed_output")
    if isinstance(parsed, list) and parsed:
        return cast(dict[str, Any], parsed[-1])
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)

    stdout = result.get("stdout", "") or ""
    if stdout.strip():
        try:
            return cast(dict[str, Any], json.loads(stdout.strip().splitlines()[-1]))
        except json.JSONDecodeError:
            logger.warning("Failed to parse skill stdout as JSON")
    return None


def _run_mock_plan_review_skill(context: dict[str, Any]) -> dict[str, Any]:
    """离线 mock：从 fixture 读取并根据 context 做最小适配。"""
    draft = _load_fixture("plan_review_draft.json")
    deviation = context.get("deviation_result", {})
    triggered = deviation.get("triggered", [])
    if triggered:
        draft["triggered_conditions"] = triggered
        draft["deviations"] = [
            f"偏离分数：{deviation.get('score')}，等级：{deviation.get('level')}，建议：{deviation.get('action')}"
        ]
    return draft


def _run_plan_review_skill(
    context: dict[str, Any],
    mock: bool,
) -> dict[str, Any] | None:
    """调用 plan-review skill 或 mock 生成复核草案。"""
    if mock:
        return _run_mock_plan_review_skill(context)

    if shutil.which("kimi") is None:
        logger.warning("Kimi CLI not found, falling back to mock mode")
        return _run_mock_plan_review_skill(context)

    result = run_skill(
        prompt="请复核以下交易计划偏离情况",
        skill_name="plan-review",
        context=context,
        timeout=120,
    )
    if not result.get("success"):
        logger.error("Plan-review skill failed: %s", result.get("stderr", ""))
        return None

    parsed = result.get("parsed_output")
    if isinstance(parsed, list) and parsed:
        return cast(dict[str, Any], parsed[-1])
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)

    stdout = result.get("stdout", "") or ""
    if stdout.strip():
        try:
            return cast(dict[str, Any], json.loads(stdout.strip().splitlines()[-1]))
        except json.JSONDecodeError:
            logger.warning("Failed to parse skill stdout as JSON")
    return None


def _build_batches(raw_batches: list[dict[str, Any]]) -> list[TradeBatch]:
    batches: list[TradeBatch] = []
    for idx, raw in enumerate(raw_batches):
        batches.append(
            TradeBatch(
                batch_id=raw.get("batch_id") or str(idx + 1),
                target_price=_to_decimal(raw.get("target_price")),
                target_price_low=_to_decimal(raw.get("target_price_low")),
                target_price_high=_to_decimal(raw.get("target_price_high")),
                allocation_pct=_to_decimal(raw.get("allocation_pct")) or Decimal("25"),
                trigger_condition=raw.get("trigger_condition"),
                notes=raw.get("notes"),
            )
        )
    return batches


def _build_trade_plan(
    plan_id: str,
    name: str,
    ticker: str,
    context: dict[str, Any],
    draft: dict[str, Any],
) -> TradePlan:
    """将 skill/mock 输出草案转换为 ``TradePlan``。"""
    source_snapshots: dict[str, str] = {}
    research_path = latest_snapshot_path("equity", ticker)
    if research_path is not None:
        source_snapshots["research"] = str(research_path)
    market_path = latest_snapshot_path("market")
    if market_path is not None:
        source_snapshots["market"] = str(market_path)
    portfolio_path = latest_snapshot_path("portfolio")
    if portfolio_path is not None:
        source_snapshots["portfolio"] = str(portfolio_path)

    return TradePlan(
        plan_id=plan_id,
        name=name,
        ticker=ticker,
        direction=draft.get("direction", "long"),
        time_window=draft.get("time_window", "3-6m"),
        research_version=draft.get("research_version", context.get("research_version", "unknown")),
        entry_logic=draft.get("entry_logic", ""),
        exit_logic=draft.get("exit_logic"),
        target_price_low=_to_decimal(draft.get("target_price_low")),
        target_price_high=_to_decimal(draft.get("target_price_high")),
        stop_loss=_to_decimal(draft.get("stop_loss")),
        take_profit=_to_decimal(draft.get("take_profit")),
        position_limit=_to_decimal(draft.get("position_limit")) or Decimal("10"),
        initial_position_pct=_to_decimal(draft.get("initial_position_pct")),
        max_position_pct=_to_decimal(draft.get("max_position_pct")),
        risk_budget=_to_decimal(draft.get("risk_budget")) or Decimal("2"),
        expected_return=_to_decimal(draft.get("expected_return")),
        invalidation_conditions=draft.get("invalidation_conditions", []),
        alternative_scenarios=draft.get("alternative_scenarios", []),
        triggers=draft.get("triggers", []),
        batch_strategy=_build_batches(draft.get("batch_strategy", [])),
        review_frequency=draft.get("review_frequency", "weekly"),
        source_snapshots=source_snapshots,
        notes=draft.get("notes"),
        status=TradePlanStatus.DRAFT,
        plan_version="1",
        metadata=SourceMetadata(
            source="climbing.plan.create",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )


@app.command("create")
def create_plan(
    ctx: typer.Context,
    ticker: str = typer.Argument(..., help="股票代码"),
    name: str = typer.Option(..., help="计划名称"),
    direction: str = typer.Option("long", help="方向：long / short"),
    time_window: str = typer.Option("3-6m", help="时间窗口"),
    research_version: str | None = typer.Option(None, help="关联研报版本，默认取最新"),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="用户确认后直接将草稿激活为 v2",
    ),
) -> None:
    """创建交易计划草案；加 --confirm 可直接激活。"""
    logger.info("Creating plan for %s (mock=%s, confirm=%s)", ticker, mock, confirm)

    context = _load_context(ticker, research_version=research_version)
    draft = _run_trade_plan_skill(ticker, context, mock=mock)
    if draft is None:
        format_result(
            ctx,
            success=False,
            message="交易计划草案生成失败",
        )
        raise typer.Exit(code=1)

    plan_id = build_plan_id(ticker, name)
    plan = _build_trade_plan(plan_id, name, ticker, context, draft)

    # 允许 CLI 显式覆盖方向与时间窗口
    if direction:
        plan.direction = direction  # type: ignore[assignment]
    if time_window:
        plan.time_window = time_window

    save_plan(plan)
    write_plans_web_summary()

    message = f"交易计划创建完成：{ticker} - {name}（草稿 v1）"
    extra: dict[str, Any] = {"plan_id": plan_id}

    if confirm:
        machine = PlanStateMachine(plan)
        machine.activate(user_confirmed=True, reason="用户创建时确认激活")
        save_plan(plan)
        write_plans_web_summary()
        message = f"交易计划创建并激活：{ticker} - {name}（v{plan.plan_version}）"
        extra["status"] = plan.status.value

    format_result(
        ctx,
        success=True,
        message=message,
        snapshot_path=plan_path(plan_id),
        version=plan.plan_version,
        extra=extra,
    )


@app.command("list")
def list_plans(ctx: typer.Context) -> None:
    """列出所有交易计划。"""
    logger.info("Listing plans")
    plans_data: list[dict[str, Any]] = []
    for plan_id in list_plan_ids():
        try:
            plan = load_plan(plan_id)
            plans_data.append(
                {
                    "plan_id": plan.plan_id,
                    "name": plan.name,
                    "ticker": plan.ticker,
                    "direction": plan.direction,
                    "status": plan.status.value,
                    "status_display": status_display_name(plan.status),
                    "plan_version": plan.plan_version,
                    "target_price_low": str(plan.target_price_low)
                    if plan.target_price_low is not None
                    else None,
                    "target_price_high": str(plan.target_price_high)
                    if plan.target_price_high is not None
                    else None,
                }
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load plan %s: %s", plan_id, exc)

    format_result(
        ctx,
        success=True,
        message=f"共 {len(plans_data)} 条交易计划。",
        extra={"plans": plans_data},
    )


@app.command("show")
def show_plan(
    ctx: typer.Context,
    plan_id: str = typer.Argument(..., help="计划ID"),
) -> None:
    """展示交易计划详情。"""
    logger.info("Showing plan: %s", plan_id)
    try:
        plan = load_plan(plan_id)
    except FileNotFoundError:
        format_result(ctx, success=False, message=f"计划不存在：{plan_id}")
        raise typer.Exit(code=1) from None

    format_result(
        ctx,
        success=True,
        message=f"计划详情：{plan.name}",
        snapshot_path=plan_path(plan_id),
        version=plan.plan_version,
        extra={
            "plan_id": plan.plan_id,
            "ticker": plan.ticker,
            "direction": plan.direction,
            "status": plan.status.value,
            "status_display": status_display_name(plan.status),
            "target_price_low": str(plan.target_price_low)
            if plan.target_price_low is not None
            else None,
            "target_price_high": str(plan.target_price_high)
            if plan.target_price_high is not None
            else None,
            "position_limit": str(plan.position_limit),
            "risk_budget": str(plan.risk_budget),
            "review_frequency": plan.review_frequency,
            "research_version": plan.research_version,
            "audit_log_count": len(plan.audit_log),
        },
    )


@app.command("transition")
def transition_plan(
    ctx: typer.Context,
    plan_id: str = typer.Argument(..., help="计划ID"),
    to_status: str = typer.Argument(..., help="目标状态"),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="用户确认后执行迁移（必须）",
    ),
    reason: str = typer.Option("", help="迁移原因"),
) -> None:
    """迁移交易计划状态；必须加 --confirm。"""
    logger.info("Transitioning plan %s to %s", plan_id, to_status)
    try:
        plan = load_plan(plan_id)
    except FileNotFoundError:
        format_result(ctx, success=False, message=f"计划不存在：{plan_id}")
        raise typer.Exit(code=1) from None

    try:
        target = TradePlanStatus(to_status)
    except ValueError:
        format_result(
            ctx,
            success=False,
            message=f"非法状态：{to_status}",
            extra={"allowed": [s.value for s in TradePlanStatus]},
        )
        raise typer.Exit(code=1) from None

    machine = PlanStateMachine(plan)
    if not machine.can_transition(target):
        format_result(
            ctx,
            success=False,
            message=f"无法从 {plan.status.value} 迁移到 {to_status}",
            extra={
                "current_status": plan.status.value,
                "allowed": [s.value for s in machine.allowed_transitions()],
            },
        )
        raise typer.Exit(code=1)

    if not confirm:
        format_result(
            ctx,
            success=False,
            message="状态迁移必须经用户确认：请加 --confirm",
            extra={
                "current_status": plan.status.value,
                "target_status": to_status,
                "requires_confirmation": True,
            },
        )
        raise typer.Exit(code=1)

    machine.transition(target, user_confirmed=True, reason=reason or None)
    save_plan(plan)
    write_plans_web_summary()
    format_result(
        ctx,
        success=True,
        message=f"计划状态已迁移：{plan.status.value}（v{plan.plan_version}）",
        snapshot_path=plan_path(plan_id),
        version=plan.plan_version,
        extra={
            "plan_id": plan.plan_id,
            "status": plan.status.value,
            "status_display": status_display_name(plan.status),
        },
    )


@app.command("check")
def check_plan(
    ctx: typer.Context,
    plan_id: str = typer.Argument(..., help="计划ID"),
    latest_price: str = typer.Option("0", help="最新价格"),
    announcement_file: Path | None = typer.Option(
        None,
        "--announcement-file",
        help="公告 JSON 文件路径（列表格式）",
    ),
    financials_file: Path | None = typer.Option(
        None,
        "--financials-file",
        help="财务 JSON 文件路径（字典格式，含 np_yoy 等）",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出复核草案（测试用）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
) -> None:
    """检查计划偏离并生成 PlanReviewSnapshot。"""
    logger.info("Checking plan: %s", plan_id)
    try:
        plan = load_plan(plan_id)
    except FileNotFoundError:
        format_result(ctx, success=False, message=f"计划不存在：{plan_id}")
        raise typer.Exit(code=1) from None

    price = Decimal(latest_price)

    latest_financials: dict[str, Any] = {}
    financials_raw = _load_json_file(financials_file)
    if isinstance(financials_raw, dict):
        latest_financials = financials_raw

    latest_announcements: list[dict[str, Any]] = []
    announcements_raw = _load_json_file(announcement_file)
    if isinstance(announcements_raw, list):
        latest_announcements = announcements_raw

    scorer = PlanDeviationScorer()
    deviation = scorer.evaluate(
        plan=plan,
        latest_price=price,
        latest_financials=latest_financials,
        latest_announcements=latest_announcements,
    )

    review_context: dict[str, Any] = {
        "plan": plan.model_dump(mode="json"),
        "latest_price": str(price),
        "deviation_result": deviation,
    }
    market = _load_latest_market()
    if market is not None:
        review_context["market_snapshot"] = market.model_dump(mode="json")
    research = _load_latest_research(plan.ticker)
    if research is not None:
        review_context["research_snapshot"] = research.model_dump(mode="json")

    draft = _run_plan_review_skill(review_context, mock=mock)

    version = generate_version(f"{plan_id}-{datetime.now().isoformat()}")
    review = PlanReviewSnapshot(
        snapshot_id=f"plan-review-{plan_id}-{version}",
        version=version,
        plan_id=plan_id,
        plan_version=plan.plan_version,
        triggered_conditions=deviation.get("triggered", []),
        deviations=[
            f"偏离分数：{deviation.get('score')}，等级：{deviation.get('level')}，建议：{deviation.get('action')}"
        ],
        recommendation=deviation.get("action", "继续持有观察"),
        suggested_action=deviation.get("action"),
        requires_user_confirmation=deviation.get("level") in ("moderate", "severe"),
        latest_price=price,
        fundamental_review=draft.get("fundamental_review") if draft else None,
        valuation_review=draft.get("valuation_review") if draft else None,
        market_review=draft.get("market_review") if draft else None,
        bull_arguments=draft.get("bull_arguments", []) if draft else [],
        bear_arguments=draft.get("bear_arguments", []) if draft else [],
        plan_change_suggestions=draft.get("plan_change_suggestions", []) if draft else [],
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
        extra={
            "score": deviation.get("score"),
            "level": deviation.get("level"),
            "triggered": deviation.get("triggered"),
            "requires_confirmation": review.requires_user_confirmation,
        },
    )


@app.command("link-transaction")
def link_transaction(
    ctx: typer.Context,
    plan_id: str = typer.Argument(..., help="计划ID"),
    transaction_id: str = typer.Argument(..., help="交易流水ID"),
    ticker: str = typer.Argument(..., help="标的代码"),
    side: str = typer.Argument(..., help="buy / sell"),
    quantity: int = typer.Argument(..., help="数量"),
    price: str = typer.Argument(..., help="成交价格"),
    fee: str = typer.Option("0", help="手续费"),
) -> None:
    """将一条交易流水关联到计划（不自动迁移状态）。"""
    logger.info("Linking transaction %s to plan %s", transaction_id, plan_id)
    try:
        plan = load_plan(plan_id)
    except FileNotFoundError:
        format_result(ctx, success=False, message=f"计划不存在：{plan_id}")
        raise typer.Exit(code=1) from None

    link_transaction_to_plan(
        plan=plan,
        transaction_id=transaction_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
    )
    save_plan(plan)
    write_plans_web_summary()

    latest_record = plan.execution_records[-1]
    format_result(
        ctx,
        success=True,
        message=f"已关联交易流水 {transaction_id} 到计划 {plan_id}",
        snapshot_path=plan_path(plan_id),
        version=plan.plan_version,
        extra={
            "execution_records_count": len(plan.execution_records),
            "plan_version_at_execution": latest_record.plan_version_at_execution,
            "execution_deviation_pct": str(latest_record.execution_deviation_pct)
            if latest_record.execution_deviation_pct is not None
            else None,
            "discipline_score": str(latest_record.discipline_score)
            if latest_record.discipline_score is not None
            else None,
        },
    )
