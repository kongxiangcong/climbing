"""数据更新 CLI。"""

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import typer

from src.analysis.plan_deviation import PlanDeviationScorer
from src.cli.formatting import format_result
from src.cli.portfolio import build_portfolio_snapshot
from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import (
    CapitalFlowAssessment,
    CapitalFlowSnapshot,
    DailyReviewSnapshot,
    DeviationAlert,
    IndexMetric,
    MacroReportSnapshot,
    MarketSnapshot,
    PortfolioSnapshot,
    ResearchAlert,
    ResearchSnapshot,
    SectorHeat,
    SourceMetadata,
)
from src.common.paths import get_data_dir
from src.common.plan_io import list_plan_ids, load_plan
from src.common.research_cache import CacheTier, ResearchCache
from src.common.snapshot_io import latest_snapshot_path, read_snapshot, write_snapshot
from src.data_standardization.market_data import build_market_snapshot_data
from src.data_standardization.price_lookup import load_latest_price
from src.data_standardization.security_master import SecurityMaster
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


def _load_latest_research(ticker: str) -> ResearchSnapshot | None:
    """读取某只股票最新的 ResearchSnapshot。"""
    path = latest_snapshot_path("equity", ticker)
    if path is None:
        return None
    return read_snapshot(path, ResearchSnapshot)


def _market_snapshot(trade_date: datetime | None = None) -> tuple[Path, str]:
    """生成市场事实快照。

    流程：从 fixture 或可选数据源拉取标准化市场数据 → 生成 MarketSnapshot
    → 写入 ``data/reports/market/{version}/snapshot.json``。
    """
    dt = trade_date.date() if trade_date else None
    data = build_market_snapshot_data(trade_date=dt)

    version = generate_version(data)

    indices = [
        IndexMetric(
            ticker=m["ticker"],
            name=m["name"],
            close=m["close"],
            change_pct=m["change_pct"],
            volume=m.get("volume"),
        )
        for m in data["indices"]
    ]
    if not indices:
        indices = [
            IndexMetric(
                ticker="000001.SH",
                name="上证指数",
                close=Decimal("3000.00"),
                change_pct=Decimal("0.00"),
            )
        ]

    sector_heat = [
        SectorHeat(
            name=s["name"],
            score=s["score"],
            change_pct=s.get("change_pct"),
        )
        for s in data["sector_heat"]
    ]

    metadata: SourceMetadata = data["metadata"]
    metadata.retrieved_at = datetime.now()

    snapshot = MarketSnapshot(
        snapshot_id=f"market-{version}",
        version=version,
        trade_date=data["trade_date"],
        indices=indices,
        breadth=data["breadth"],
        total_turnover=data["total_turnover"],
        sector_heat=sector_heat,
        margin_balance=data["margin_balance"],
        northbound_flow=data["northbound_flow"],
        etf_flow=data["etf_flow"],
        sentiment_score=data["sentiment_score"],
        risk_appetite=data["risk_appetite"],
        metadata=metadata,
    )
    path = write_snapshot(snapshot, "market", use_version_dir=True)
    _write_web_market_summary(snapshot)
    return path, version


def _write_web_market_summary(snapshot: MarketSnapshot) -> Path:
    """将最新 MarketSnapshot 摘要写入 web/public，供前端静态读取。"""
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "market-summary.json"

    temperature_label = snapshot.risk_appetite or "未知"
    temperature_score = snapshot.sentiment_score

    summary = {
        "last_snapshot_at": snapshot.created_at.isoformat(),
        "version": snapshot.version,
        "trade_date": snapshot.trade_date.isoformat(),
        "indices": [
            {
                "ticker": i.ticker,
                "name": i.name,
                "close": str(i.close),
                "change_pct": str(i.change_pct),
            }
            for i in snapshot.indices
        ],
        "total_turnover": str(snapshot.total_turnover) if snapshot.total_turnover is not None else None,
        "breadth": snapshot.breadth,
        "sector_heat": [
            {"name": s.name, "score": s.score, "change_pct": str(s.change_pct) if s.change_pct is not None else None}
            for s in snapshot.sector_heat
        ],
        "sentiment_score": temperature_score,
        "temperature_label": temperature_label,
    }
    web_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote market summary for web -> %s", web_path)
    return web_path


def _portfolio_snapshot() -> tuple[Path, str]:
    """生成账户事实快照；优先从用户交易流水推导。"""
    from src.data_standardization.transaction_loader import load_transactions

    tx_path = get_data_dir("user") / "transactions.csv"
    transactions: list[Any] = []
    if tx_path.exists():
        transactions = load_transactions(tx_path, raw_source=str(tx_path))

    snapshot = build_portfolio_snapshot(transactions)
    path = write_snapshot(snapshot, "portfolio")

    # 同步前端可读取的摘要 JSON
    from src.cli.portfolio import _write_web_portfolio_summary

    _write_web_portfolio_summary(snapshot)
    return path, snapshot.version


def _collect_watchlist_tickers(portfolio: PortfolioSnapshot) -> set[str]:  # type: ignore[name-defined]
    """从持仓与激活中的计划收集需要监控的标的。"""
    tickers: set[str] = {p.ticker for p in portfolio.positions}
    for plan_id in list_plan_ids():
        try:
            plan = load_plan(plan_id)
            tickers.add(plan.ticker)
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to load plan %s: %s", plan_id, exc)
    return tickers


def _check_plan_deviations() -> list[DeviationAlert]:
    """检查所有激活/部分触发计划的偏离情况。"""
    alerts: list[DeviationAlert] = []
    scorer = PlanDeviationScorer()

    for plan_id in list_plan_ids():
        try:
            plan = load_plan(plan_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load plan %s: %s", plan_id, exc)
            continue

        if plan.status.value not in {"active", "partially_triggered"}:
            continue

        price = load_latest_price(plan.ticker)
        if price is None:
            research = _load_latest_research(plan.ticker)
            if research is not None and research.stock_price_data is not None:
                current_price = research.stock_price_data.current_price
                if current_price is not None and current_price > 0:
                    try:
                        price = Decimal(str(current_price))
                    except Exception:
                        price = None
        if price is None:
            logger.info("Skipping deviation check for %s: no latest price", plan.ticker)
            continue

        result = scorer.evaluate(
            plan=plan,
            latest_price=price,
            latest_financials={},
            latest_announcements=[],
        )
        if result.get("triggered"):
            alerts.append(
                DeviationAlert(
                    plan_id=plan_id,
                    reason=f"{result['level']}: {', '.join(result['triggered'])}",
                    severity=result["level"],
                )
            )

    return alerts


def _check_stale_research(tickers: set[str]) -> list[ResearchAlert]:
    """基于三级缓存规则检查需要重跑的研报。"""
    alerts: list[ResearchAlert] = []
    for ticker in sorted(tickers):
        cache = ResearchCache(ticker)
        tier, _ = cache.determine_tier()
        if tier == CacheTier.STALE:
            alerts.append(
                ResearchAlert(
                    ticker=ticker,
                    reason="研报过期或遇到事件需重跑",
                )
            )
        elif tier == CacheTier.NON_EXISTENT:
            alerts.append(
                ResearchAlert(
                    ticker=ticker,
                    reason="尚无研报，建议先跑深度研究",
                )
            )
    return alerts


def _load_latest_announcements() -> list[dict[str, Any]]:
    """加载最新公告 fixture（当前为离线占位）。"""
    raw = _load_json_file(settings.project_root / "tests" / "fixtures" / "announcements.json")
    if isinstance(raw, list):
        return raw
    return []


def _run_mock_daily_review(context: dict[str, Any]) -> dict[str, Any]:
    """调用 skills/daily-review/scripts/mock_daily_review.py 离线生成复盘草案。"""
    script = settings.project_root / "skills" / "daily-review" / "scripts" / "mock_daily_review.py"
    if not script.exists():
        logger.warning("daily-review mock script not found, using fixture fallback")
        return _load_fixture("daily_review.json")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        tmp.write(json.dumps(context, ensure_ascii=False, indent=2))
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(tmp_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            logger.warning("daily-review mock script failed: %s", proc.stderr)
            return _load_fixture("daily_review.json")
        return json.loads(proc.stdout)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to run daily-review mock script: %s", exc)
        return _load_fixture("daily_review.json")
    finally:
        tmp_path.unlink(missing_ok=True)


def _run_daily_review_skill(
    context: dict[str, Any],
    mock: bool,
) -> dict[str, Any] | None:
    """调用 daily-review skill 或 mock 生成复盘草案。"""
    if mock or shutil.which("kimi") is None:
        if not mock:
            logger.warning("Kimi CLI not found, falling back to mock mode")
        return _run_mock_daily_review(context)

    from src.common.skill_runner import run_skill

    result = run_skill(
        prompt="请基于今日市场、持仓和触发器结果生成每日复盘",
        skill_name="daily-review",
        context=context,
        timeout=120,
    )
    if not result.get("success"):
        logger.error("daily-review skill failed: %s", result.get("stderr", ""))
        return None

    parsed = result.get("parsed_output")
    if isinstance(parsed, list) and parsed:
        return parsed[-1]
    if isinstance(parsed, dict):
        return parsed

    stdout = result.get("stdout", "") or ""
    if stdout.strip():
        try:
            return json.loads(stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            logger.warning("Failed to parse daily-review skill stdout as JSON")
    return None


def _parse_deviation_alert(raw: dict[str, Any]) -> DeviationAlert | None:
    """安全解析偏离告警字典；格式错误时记录日志并跳过。"""
    try:
        return DeviationAlert.model_validate(raw)
    except Exception as exc:  # pragma: no cover
        logger.warning("Skipping malformed plan_deviation entry: %s (%s)", raw, exc)
        return None


def _parse_research_alert(raw: dict[str, Any]) -> ResearchAlert | None:
    """安全解析研究过期告警字典；格式错误时记录日志并跳过。"""
    try:
        return ResearchAlert.model_validate(raw)
    except Exception as exc:  # pragma: no cover
        logger.warning("Skipping malformed stale_research entry: %s (%s)", raw, exc)
        return None


def _daily_review_snapshot(
    market: MarketSnapshot,
    portfolio: PortfolioSnapshot,
    mock: bool = False,
) -> tuple[Path, str]:
    """生成每日复盘分析快照。

    流程：收集监控标的 → 检查计划偏离 → 检查过期研究 → 调用 daily-review skill/mock
    → 写入 ``data/reports/daily_review/{version}.json``。
    """
    watchlist_tickers = _collect_watchlist_tickers(portfolio)
    plan_deviations = _check_plan_deviations()
    stale_research = _check_stale_research(watchlist_tickers)

    context: dict[str, Any] = {
        "market_snapshot": market.model_dump(mode="json"),
        "portfolio_snapshot": portfolio.model_dump(mode="json"),
        "plan_deviations": [d.model_dump(mode="json") for d in plan_deviations],
        "stale_research": [r.model_dump(mode="json") for r in stale_research],
        "latest_announcements": _load_latest_announcements(),
        "watchlist": sorted(watchlist_tickers),
    }

    draft = _run_daily_review_skill(context, mock=mock)
    if draft is None:
        draft = _load_fixture("daily_review.json")

    version = generate_version(context)
    trade_date = market.trade_date

    snapshot = DailyReviewSnapshot(
        snapshot_id=f"daily-review-{version}",
        version=version,
        trade_date=trade_date,
        highlights=draft.get("highlights", []),
        sentiment=draft.get("sentiment", ""),
        portfolio_risk=draft.get("portfolio_risk", {}),
        plan_deviations=[
            alert
            for d in draft.get("plan_deviations", [])
            if (alert := _parse_deviation_alert(d)) is not None
        ],
        stale_research=[
            alert
            for r in draft.get("stale_research", [])
            if (alert := _parse_research_alert(r)) is not None
        ],
        watchlist=draft.get("watchlist", sorted(watchlist_tickers)),
        metadata=SourceMetadata(
            source="climbing.update.daily_review",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "daily_review")
    _write_daily_review_web_summary(snapshot)
    return path, version


def _write_daily_review_web_summary(snapshot: DailyReviewSnapshot) -> Path:
    """将最新 DailyReviewSnapshot 摘要写入 web/public，供前端静态读取。"""
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "daily-review-summary.json"

    summary = {
        "last_snapshot_at": snapshot.created_at.isoformat(),
        "version": snapshot.version,
        "trade_date": snapshot.trade_date.isoformat(),
        "highlights": snapshot.highlights,
        "sentiment": snapshot.sentiment,
        "portfolio_risk": snapshot.portfolio_risk,
        "plan_deviations": [d.model_dump(mode="json") for d in snapshot.plan_deviations],
        "stale_research": [r.model_dump(mode="json") for r in snapshot.stale_research],
        "watchlist": snapshot.watchlist,
        "pending_counts": {
            "stocks_needing_review": len(snapshot.watchlist),
            "plan_deviations": len(snapshot.plan_deviations),
            "expired_research": len(snapshot.stale_research),
        },
    }
    web_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote daily review summary for web -> %s", web_path)
    return web_path


def _write_system_status(snapshots: list[dict[str, Any]]) -> Path:
    """将最新快照元数据写入前端可读取的 status 文件。"""
    status: dict[str, Any] = {
        "last_snapshot_at": datetime.now().isoformat(),
        "last_snapshot_version": snapshots[0]["version"] if snapshots else "",
        "snapshots": snapshots,
    }
    # 同时写入 data/reports 与 web/public，方便前端直接静态读取
    data_path = get_data_dir("reports") / "system-status.json"
    data_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "system-status.json"
    web_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return web_path


@app.command("daily")
def daily_update(
    ctx: typer.Context,
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
) -> None:
    """收盘后一键更新：市场事实、持仓事实、触发器检查、每日复盘。"""
    logger.info("Starting daily update (mock=%s)", mock)
    try:
        market_path, market_version = _market_snapshot()
    except RuntimeError as exc:
        logger.error("Market data fetch failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"市场数据刷新失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    portfolio_path, portfolio_version = _portfolio_snapshot()

    market = read_snapshot(market_path, MarketSnapshot)
    portfolio = read_snapshot(portfolio_path, PortfolioSnapshot)
    try:
        review_path, review_version = _daily_review_snapshot(market, portfolio, mock=mock)
    except Exception as exc:
        logger.error("Daily review generation failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"每日复盘生成失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    snapshots: list[dict[str, Any]] = [
        {"report_type": "market", "snapshot_path": str(market_path), "version": market_version},
        {"report_type": "portfolio", "snapshot_path": str(portfolio_path), "version": portfolio_version},
        {"report_type": "daily_review", "snapshot_path": str(review_path), "version": review_version},
    ]
    _write_system_status(snapshots)
    format_result(
        ctx,
        success=True,
        message="Daily update completed.",
        extra={"snapshots": snapshots},
    )


@app.command("monthly")
def monthly_update(
    ctx: typer.Context,
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
    report_month: str | None = typer.Option(
        None,
        "--month",
        help="报告月份，格式 YYYY-MM；默认上月",
    ),
) -> None:
    """月更任务：生成宏观资金流事实快照与宏观月报叙事快照。"""
    logger.info("Starting monthly update (mock=%s, month=%s)", mock, report_month)

    try:
        cf_path, cf_snapshot = _capital_flow_snapshot(report_month=report_month)
    except Exception as exc:
        logger.error("Capital flow standardization failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"宏观事实表生成失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    try:
        macro_path, macro_version = _macro_report_snapshot(
            capital_flow=cf_snapshot, mock=mock
        )
    except Exception as exc:
        logger.error("Macro report generation failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"宏观月报生成失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    _write_macro_report_web_summary(cf_snapshot)

    snapshots: list[dict[str, Any]] = [
        {
            "report_type": "capital_flow",
            "snapshot_path": str(cf_path),
            "version": cf_snapshot.version,
        },
        {
            "report_type": "macro_report",
            "snapshot_path": str(macro_path),
            "version": macro_version,
        },
    ]
    _write_system_status(snapshots)
    format_result(
        ctx,
        success=True,
        message="Monthly update completed.",
        extra={"snapshots": snapshots},
    )


def _capital_flow_snapshot(
    report_month: str | None = None,
) -> tuple[Path, CapitalFlowSnapshot]:
    """生成宏观资金流事实快照。"""
    from src.data_standardization.capital_flow import CapitalFlowStandardizer

    standardizer = CapitalFlowStandardizer()
    snapshot = standardizer.build_snapshot(report_month=report_month)
    path = write_snapshot(snapshot, "capital_flow")
    return path, snapshot


def _run_mock_capital_flow(context: dict[str, Any]) -> dict[str, Any]:
    """调用 skills/capital-flow/scripts/mock_capital_flow.py 离线生成月报草案。"""
    script = settings.project_root / "skills" / "capital-flow" / "scripts" / "mock_capital_flow.py"
    if not script.exists():
        logger.warning("capital-flow mock script not found, using fixture fallback")
        return _load_fixture("capital_flow.json")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        tmp.write(json.dumps(context, ensure_ascii=False, indent=2))
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(tmp_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            logger.warning("capital-flow mock script failed: %s", proc.stderr)
            return _load_fixture("capital_flow.json")
        return cast(dict[str, Any], json.loads(proc.stdout))
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to run capital-flow mock script: %s", exc)
        return _load_fixture("capital_flow.json")
    finally:
        tmp_path.unlink(missing_ok=True)


def _run_capital_flow_skill(
    context: dict[str, Any],
    mock: bool,
) -> dict[str, Any] | None:
    """调用 capital-flow skill 或 mock 生成月报叙事草案。"""
    if mock or shutil.which("kimi") is None:
        if not mock:
            logger.warning("Kimi CLI not found, falling back to mock mode")
        return _run_mock_capital_flow(context)

    from src.common.skill_runner import run_skill

    result = run_skill(
        prompt="请基于以下宏观事实生成资金面四问月报",
        skill_name="capital-flow",
        context=context,
        timeout=120,
    )
    if not result.get("success"):
        logger.error("capital-flow skill failed: %s", result.get("stderr", ""))
        return None

    parsed = result.get("parsed_output")
    if isinstance(parsed, list) and parsed:
        return cast(dict[str, Any], parsed[-1])
    if isinstance(parsed, dict):
        return parsed

    stdout = result.get("stdout", "") or ""
    if stdout.strip():
        try:
            return cast(dict[str, Any], json.loads(stdout.strip().splitlines()[-1]))
        except json.JSONDecodeError:
            logger.warning("Failed to parse capital-flow skill stdout as JSON")
    return None


def _macro_report_snapshot(
    capital_flow: CapitalFlowSnapshot,
    mock: bool,
) -> tuple[Path, str]:
    """生成宏观月报叙事快照。"""
    from src.report_generation.capital_flow_report import CapitalFlowReportGenerator

    context = capital_flow.model_dump(mode="json")
    draft = _run_capital_flow_skill(context, mock=mock)

    if draft is None:
        draft = {}

    summary = draft.get("summary") or (
        f"{capital_flow.report_month} 宏观月报占位：增长 {capital_flow.growth_label}，"
        f"通胀 {capital_flow.inflation_label}，流动性 {capital_flow.liquidity_label}，"
        f"市场结构 {capital_flow.market_structure_label}。"
    )
    outlook = draft.get("outlook") or "请补充展望。"
    risks = draft.get("risks") or []
    recommendations = draft.get("recommendations") or []

    four_questions_raw = draft.get("four_questions")
    if four_questions_raw:
        four_questions = [
            CapitalFlowAssessment.model_validate(q) for q in four_questions_raw
        ]
    else:
        four_questions = capital_flow.assessments

    version_data = {
        "report_month": capital_flow.report_month,
        "capital_flow_snapshot_id": capital_flow.snapshot_id,
        "summary": summary,
        "four_questions": [q.model_dump(mode="json") for q in four_questions],
    }
    version = generate_version(version_data)

    snapshot = MacroReportSnapshot(
        snapshot_id=f"macro-report-{version}",
        version=version,
        report_month=capital_flow.report_month,
        capital_flow_snapshot_id=capital_flow.snapshot_id,
        summary=summary,
        four_questions=four_questions,
        outlook=outlook,
        risks=risks,
        recommendations=recommendations,
        metadata=SourceMetadata(
            source="climbing.update.macro_report",
            retrieved_at=datetime.now(),
            version="1.0.0",
            tier=1,
        ),
    )
    path = write_snapshot(snapshot, "macro_report")

    generator = CapitalFlowReportGenerator()
    report_md = generator.generate(capital_flow=capital_flow, macro_report=snapshot)
    md_path = get_data_dir("reports") / "macro" / f"{version}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(report_md, encoding="utf-8")
    logger.info("Wrote macro report markdown -> %s", md_path)

    return path, version


def _write_macro_report_web_summary(snapshot: CapitalFlowSnapshot) -> Path:
    """将最新宏观月报摘要写入 web/public，供前端静态读取。"""
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "macro-report.json"

    raw = snapshot.model_dump(mode="json")
    # 把 tier 同时暴露为 authority_tier，便于前端展示
    for ind in raw.get("indicators", []):
        meta = ind.get("metadata", {})
        meta["authority_tier"] = meta.get("tier")

    # 提供图表可用的时间序列（ fixture 中可能包含）
    fixture = _load_fixture("capital_flow.json")
    indicator_history = fixture.get("indicator_history", [])

    summary = {
        "report_month": snapshot.report_month,
        "last_snapshot_at": snapshot.created_at.isoformat(),
        "version": snapshot.version,
        "source": snapshot.metadata.source,
        "retrieved_at": snapshot.metadata.retrieved_at.isoformat(),
        "authority_tier": snapshot.metadata.tier,
        "indicators": raw.get("indicators", []),
        "indicator_history": indicator_history,
        "four_questions": [a.model_dump(mode="json") for a in snapshot.assessments],
        "growth_label": snapshot.growth_label,
        "inflation_label": snapshot.inflation_label,
        "liquidity_label": snapshot.liquidity_label,
        "market_structure_label": snapshot.market_structure_label,
    }
    web_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote macro report summary for web -> %s", web_path)
    return web_path


@app.command("daily-review")
def daily_review(ctx: typer.Context) -> None:
    """生成每日复盘快照（agent 可消费）。"""
    from src.common.models import DailyReviewSnapshot

    fixture = _load_fixture("daily_review.json")
    version = generate_version(fixture)
    trade_date = datetime.strptime(
        fixture.get("trade_date", datetime.now().strftime("%Y-%m-%d")),
        "%Y-%m-%d",
    ).date()
    snapshot = DailyReviewSnapshot(
        snapshot_id=f"daily-review-{version}",
        version=version,
        trade_date=trade_date,
        highlights=fixture.get("highlights", []),
        sentiment=fixture.get("sentiment", ""),
        portfolio_risk=fixture.get("portfolio_risk", {}),
        plan_deviations=[
            DeviationAlert(**d) for d in fixture.get("plan_deviations", [])
        ],
        stale_research=[
            ResearchAlert(**r) for r in fixture.get("stale_research", [])
        ],
        watchlist=fixture.get("watchlist", []),
        metadata=SourceMetadata(
            source="climbing.update.daily_review",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "daily_review")
    format_result(
        ctx,
        success=True,
        message="Daily review snapshot generated.",
        snapshot_path=path,
        version=version,
    )


@app.command("securities")
def update_securities(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="仅预览，不写入文件"),
    manual_ticker: list[str] = typer.Option(
        [],
        "--manual-ticker",
        help="手动指定未识别代码，格式 CODE:MARKET:NAME[:ASSET_CLASS]",
    ),
) -> None:
    """从 config/tickers.yaml 刷新证券主数据表。"""
    logger.info("Updating security master")

    manual_map: dict[str, dict[str, Any]] = {}
    for mt in manual_ticker:
        parts = mt.split(":")
        if len(parts) < 3:
            format_result(
                ctx,
                success=False,
                message=(
                    f"手动代码格式错误：{mt}，"
                    "应为 CODE:MARKET:NAME[:ASSET_CLASS]"
                ),
            )
            raise typer.Exit(code=1)
        code, market, name = parts[0].strip().upper(), parts[1].strip().upper(), parts[2].strip()
        asset_class = parts[3].strip().lower() if len(parts) > 3 else "stock"
        manual_map[code] = {"market": market, "name": name, "asset_class": asset_class}

    master = SecurityMaster()
    path, securities, unrecognized, version = master.add_from_watchlist(
        manual_tickers=manual_map, dry_run=dry_run
    )

    if unrecognized:
        msg = (
            f"以下代码无法自动识别，请确认后重试：{', '.join(unrecognized)}。"
            "可使用 --manual-ticker CODE:MARKET:NAME 指定。"
        )
        format_result(
            ctx,
            success=False,
            message=msg,
            extra={"needs_confirmation": True, "unrecognized_tickers": unrecognized},
        )
        raise typer.Exit(code=1)

    if dry_run:
        format_result(
            ctx,
            success=True,
            message=f"预览：将写入 {len(securities)} 条证券。",
            extra={"securities": [s.ticker for s in securities]},
        )
        return

    # 同时输出一份 web/public 下的 JSON，供前端静态读取
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_json_path = web_public / "security-master.json"
    shutil.copy2(master.json_path, web_json_path)
    logger.info("Copied security master JSON -> %s", web_json_path)

    format_result(
        ctx,
        success=True,
        message=f"证券主数据刷新完成：{len(securities)} 条。",
        snapshot_path=path,
        version=version,
        extra={"securities": [s.ticker for s in securities]},
    )
