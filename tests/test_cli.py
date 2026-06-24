"""CLI worker 集成测试：验证命令生成的 snapshot 符合 schema。"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.common.config import settings
from src.common.models import (
    CapitalFlowSnapshot,
    DailyReviewSnapshot,
    InspectionSnapshot,
    MacroReportSnapshot,
    MarketSnapshot,
    PlanReviewSnapshot,
    PortfolioSnapshot,
    ResearchSnapshot,
    SourceMetadata,
    TradePlan,
)
from src.common.snapshot_io import read_snapshot, write_snapshot

PROJECT_ROOT = settings.project_root
PYTHON = sys.executable


def _run(*args: str) -> dict[str, Any]:
    """调用 CLI 并解析 JSON 输出。"""
    cmd = [PYTHON, "-m", "src.cli.main", "--format", "json", *args]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}\nstdout: {result.stdout}"
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def _write_stale_research_snapshot(ticker: str, version: str, created_at: datetime) -> Path:
    """在 equity 目录下写入一份过期的 ResearchSnapshot，用于每日复盘 stale 检测。"""
    snapshot = ResearchSnapshot(
        snapshot_id=f"research-{ticker}-{version}",
        report_type="research",
        version=version,
        ticker=ticker,
        summary="stale snapshot for daily review test",
        metadata=SourceMetadata(source="test", retrieved_at=created_at),
        created_at=created_at,
    )
    return write_snapshot(snapshot, "equity", ticker)


def test_update_daily_generates_market_portfolio_and_review_snapshots() -> None:
    # 准备持仓流水
    fixture_tx = PROJECT_ROOT / "tests" / "fixtures" / "transactions.csv"
    _run("portfolio", "transactions", str(fixture_tx))

    # 创建并激活一个 000725.SZ 交易计划，使其进入偏离检查范围
    create_data = _run(
        "plan",
        "create",
        "000725.SZ",
        "--name",
        "daily-review-test",
        "--mock",
        "--confirm",
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    # 写入一份过期的 000725.SZ 研报，触发 stale_research
    stale_version = "20990101000000-stale"
    _write_stale_research_snapshot(
        "000725.SZ",
        stale_version,
        created_at=datetime.now() - timedelta(days=30),
    )

    data = _run("update", "daily", "--mock")
    assert data["success"] is True
    snapshots = {s["report_type"]: s for s in data["snapshots"]}
    assert "market" in snapshots
    assert "portfolio" in snapshots
    assert "daily_review" in snapshots

    # 命令输出为 JSON，包含三个 snapshot 的路径和版本
    market_info = snapshots["market"]
    portfolio_info = snapshots["portfolio"]
    review_info = snapshots["daily_review"]
    assert "snapshot_path" in market_info
    assert "version" in market_info
    assert "snapshot_path" in portfolio_info
    assert "version" in portfolio_info
    assert "snapshot_path" in review_info
    assert "version" in review_info

    market_path = Path(market_info["snapshot_path"])
    # MarketSnapshot 写入 data/reports/market/{version}/snapshot.json
    assert market_path.parent.name == market_info["version"]
    assert market_path.name == "snapshot.json"

    market = read_snapshot(market_path, MarketSnapshot)
    assert market.report_type == "market"
    assert market.indices
    assert market.total_turnover is not None
    assert market.breadth
    assert {"advancers", "decliners", "unchanged"}.issubset(set(market.breadth))
    assert market.sector_heat
    assert market.margin_balance is not None
    assert market.northbound_flow is not None
    assert market.etf_flow is not None
    assert market.sentiment_score is not None
    assert market.risk_appetite is not None
    assert market.metadata.source
    assert market.metadata.retrieved_at is not None

    portfolio = read_snapshot(
        Path(portfolio_info["snapshot_path"]), PortfolioSnapshot
    )
    assert portfolio.report_type == "portfolio"

    review = read_snapshot(Path(review_info["snapshot_path"]), DailyReviewSnapshot)
    assert review.report_type == "daily_review"
    assert review.trade_date == market.trade_date
    assert review.highlights
    assert review.sentiment
    assert review.portfolio_risk
    # PRD 要求至少包含三类待复核提示字段
    assert isinstance(review.plan_deviations, list)
    assert isinstance(review.stale_research, list)
    assert isinstance(review.watchlist, list)

    # 在已激活计划 + 过期研报的 fixture 下，应产生非空的偏离与过期提示
    assert any(d.plan_id == plan_id for d in review.plan_deviations)
    assert any(r.ticker == "000725.SZ" for r in review.stale_research)

    # 复盘生成不应修改任何交易计划或持仓：计划版本应保持 v2，持仓标的数量不变
    plan = TradePlan.model_validate_json(
        (PROJECT_ROOT / "data" / "user" / "plans" / f"{plan_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan.status.value == "active"
    assert plan.plan_version == "2"
    assert len(portfolio.positions) > 0


def test_inspect_intent_generates_one_click_summary_without_mutating_plans() -> None:
    fixture_tx = PROJECT_ROOT / "tests" / "fixtures" / "transactions.csv"
    _run("portfolio", "transactions", str(fixture_tx))

    create_data = _run(
        "plan",
        "create",
        "000725.SZ",
        "--name",
        "inspection-test-plan",
        "--mock",
        "--confirm",
    )
    plan_path = Path(create_data["snapshot_path"])
    before_plan = json.loads(plan_path.read_text(encoding="utf-8"))

    stale_version = "20990101000000-inspect"
    _write_stale_research_snapshot(
        "000725.SZ",
        stale_version,
        created_at=datetime.now() - timedelta(days=30),
    )

    data = _run("inspect", "--intent", "climbing", "--mock")

    assert data["success"] is True
    assert data["intent"] == "climbing"
    assert data["route"] == "one_click_inspection"
    assert data["summary"]["market_status"]
    assert data["summary"]["portfolio_status"]
    assert data["summary"]["plan_deviations"] >= 1
    assert data["summary"]["expired_research"] >= 1
    assert data["summary"]["stocks_needing_review"] >= 1
    assert len(data["risk_reminders"]) >= 3
    assert all(reminder["blocking"] is False for reminder in data["risk_reminders"])

    snapshot = read_snapshot(Path(data["snapshot_path"]), InspectionSnapshot)
    assert snapshot.report_type == "inspection"
    assert snapshot.intent == "climbing"
    assert snapshot.summary.plan_deviations >= 1
    assert snapshot.summary.expired_research >= 1
    assert {s["report_type"] for s in snapshot.generated_snapshots} == {
        "market",
        "portfolio",
        "daily_review",
    }

    web_json = PROJECT_ROOT / "web" / "public" / "inspection-summary.json"
    assert web_json.exists()
    loaded = json.loads(web_json.read_text(encoding="utf-8"))
    assert loaded["summary"]["stocks_needing_review"] >= 1

    after_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert after_plan["status"] == before_plan["status"] == "active"
    assert after_plan["plan_version"] == before_plan["plan_version"] == "2"
    assert len(after_plan["audit_log"]) == len(before_plan["audit_log"])


def test_update_daily_fails_gracefully_when_market_fixture_missing(
    tmp_path: Path,
) -> None:
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "market_snapshot.json"
    backup = tmp_path / "market_snapshot.json.bak"
    shutil.copy2(fixture, backup)
    try:
        fixture.unlink()
        result = subprocess.run(
            [PYTHON, "-m", "src.cli.main", "--format", "json", "update", "daily"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert "No market data provider succeeded" in data["message"]
    finally:
        shutil.copy2(backup, fixture)


def test_update_daily_review_generates_daily_review_snapshot() -> None:
    data = _run("update", "daily-review")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    review = read_snapshot(snapshot_path, DailyReviewSnapshot)
    assert review.report_type == "daily_review"


def test_analyze_stock_generates_research_snapshot() -> None:
    ticker = "000725.SZ"
    data = _run("analyze", "stock", ticker, "--mock", "--force")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    # 新路径结构: data/reports/equity/{ticker}/{version}/snapshot.json
    assert snapshot_path.name == "snapshot.json"
    assert snapshot_path.parent.name != ticker
    assert snapshot_path.exists()

    research = read_snapshot(snapshot_path, ResearchSnapshot)
    assert research.report_type == "research"
    assert research.ticker == ticker

    # Slice 5b: 校验 equity-researcher 13-section 扩展字段已生成
    assert research.research_metadata is not None
    assert research.core_narrative is not None
    assert len(research.six_dimensions_typed) == 6
    assert research.investment_logic is not None
    assert len(research.investment_thesis_table) == 4
    assert research.company_overview is not None
    assert research.financial_data is not None
    assert research.valuation_data is not None
    assert len(research.catalyst_calendar) >= 4
    assert research.industry_supply_chain is not None
    assert research.stock_price_data is not None

    report_dir = snapshot_path.parent
    assert (report_dir / "report.pdf").exists()
    assert (report_dir / "qa_check.json").exists()
    assert (report_dir / "references.json").exists()
    assert research.pdf_path == str(report_dir / "report.pdf")


def test_analyze_stock_second_run_uses_cache() -> None:
    ticker = "CLI-CACHE.SZ"
    first = _run("analyze", "stock", ticker, "--mock")
    assert first["success"] is True
    first_version = first["version"]

    second = _run("analyze", "stock", ticker, "--mock")
    assert second["success"] is True
    assert second["version"] == first_version
    assert second["snapshot_path"] == first["snapshot_path"]


def test_analyze_stock_force_regenerates() -> None:
    ticker = "CLI-FORCE.SZ"
    first = _run("analyze", "stock", ticker, "--mock")
    assert first["success"] is True
    first_version = first["version"]

    forced = _run("analyze", "stock", ticker, "--mock", "--force")
    assert forced["success"] is True
    assert forced["version"] != first_version


def test_portfolio_transactions_generates_portfolio_snapshot(tmp_path: Path) -> None:
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "transactions.csv"
    data = _run("portfolio", "transactions", str(fixture))
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    portfolio = read_snapshot(snapshot_path, PortfolioSnapshot)
    assert portfolio.report_type == "portfolio"
    tickers = {p.ticker for p in portfolio.positions}
    assert "000725.SZ" in tickers


def test_plan_create_and_check_generates_trade_plan_and_review() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "integration-test-plan", "--mock"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]
    plan_path = Path(create_data["snapshot_path"])
    plan = TradePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    assert plan.ticker == "000725.SZ"
    assert plan.status.value == "draft"
    assert plan.plan_version == "1"
    assert plan.batch_strategy

    # check 生成 PlanReviewSnapshot
    check_data = _run("plan", "check", plan_id, "--latest-price", "5.2")
    assert check_data["success"] is True
    review_path = Path(check_data["snapshot_path"])
    review = read_snapshot(review_path, PlanReviewSnapshot)
    assert review.report_type == "plan_review"
    assert review.plan_id == plan_id


def test_plan_create_with_confirm_activates_plan() -> None:
    create_data = _run(
        "plan",
        "create",
        "000725.SZ",
        "--name",
        "confirmed-test-plan",
        "--mock",
        "--confirm",
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]
    plan_path = Path(create_data["snapshot_path"])
    plan = TradePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    assert plan.status.value == "active"
    assert plan.plan_version == "2"


def test_plan_transition_requires_confirmation() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "transition-test", "--mock"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    # 不加 --confirm 必须失败
    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "src.cli.main",
            "--format",
            "json",
            "plan",
            "transition",
            plan_id,
            "active",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data.get("requires_confirmation") is True

    # 加 --confirm 成功迁移
    transition_data = _run(
        "plan", "transition", plan_id, "active", "--confirm", "--reason", "用户确认"
    )
    assert transition_data["success"] is True
    plan = TradePlan.model_validate_json(
        Path(transition_data["snapshot_path"]).read_text(encoding="utf-8")
    )
    assert plan.status.value == "active"
    assert plan.plan_version == "2"
    assert any(entry.to_status.value == "active" for entry in plan.audit_log)


def test_plan_show_and_list() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "list-test", "--mock", "--confirm"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    show_data = _run("plan", "show", plan_id)
    assert show_data["success"] is True
    assert show_data["plan_id"] == plan_id
    assert show_data["status"] == "active"

    list_data = _run("plan", "list")
    assert list_data["success"] is True
    assert any(p["plan_id"] == plan_id for p in list_data["plans"])


def test_plan_check_outputs_price_trigger() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "price-trigger-test", "--mock"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    check_data = _run("plan", "check", plan_id, "--latest-price", "5.2", "--mock")
    assert check_data["success"] is True
    assert check_data["level"] in ("slight", "moderate", "severe")
    assert any("价格触发" in t for t in check_data["triggered"])

    review_path = Path(check_data["snapshot_path"])
    review = read_snapshot(review_path, PlanReviewSnapshot)
    assert review.report_type == "plan_review"
    assert review.plan_id == plan_id
    assert review.fundamental_review is not None


def test_plan_check_announcement_keyword_triggers_deviation() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "announcement-trigger-test", "--mock"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    announcement_file = str(PROJECT_ROOT / "tests" / "fixtures" / "announcements.json")
    check_data = _run(
        "plan",
        "check",
        plan_id,
        "--latest-price",
        "4.5",
        "--announcement-file",
        announcement_file,
        "--mock",
    )
    assert check_data["success"] is True
    assert any("事件触发" in t or "立案调查" in t for t in check_data["triggered"])
    assert check_data["score"] is not None and check_data["score"] > 0
    assert check_data["level"] in ("slight", "moderate", "severe")


def test_plan_link_transaction_records_execution_deviation() -> None:
    create_data = _run(
        "plan", "create", "000725.SZ", "--name", "link-transaction-test", "--mock", "--confirm"
    )
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]

    link_data = _run(
        "plan",
        "link-transaction",
        plan_id,
        "tx-100",
        "000725.SZ",
        "buy",
        "100",
        "4.85",
        "--fee",
        "5",
    )
    assert link_data["success"] is True
    assert link_data["plan_version_at_execution"] == "2"
    assert link_data["execution_deviation_pct"] is not None
    assert link_data["discipline_score"] is not None


def test_update_securities_generates_security_master() -> None:
    data = _run("update", "securities")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    assert snapshot_path.exists()
    assert snapshot_path.name == "security_master.parquet"

    df = pd.read_parquet(snapshot_path)
    required = {
        "ticker",
        "name",
        "market",
        "sector",
        "industry",
        "tags",
        "source",
        "retrieved_at",
        "version",
    }
    assert required.issubset(set(df.columns))
    assert not df.empty
    assert "000725.SZ" in df["ticker"].values
    assert "600519.SH" in df["ticker"].values


def test_update_securities_copies_json_for_web() -> None:
    data = _run("update", "securities")
    assert data["success"] is True
    web_json = settings.project_root / "web" / "public" / "security-master.json"
    assert web_json.exists()
    loaded = json.loads(web_json.read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    assert any(item["ticker"] == "000725.SZ" for item in loaded)


def test_update_securities_manual_ticker_for_unrecognized() -> None:
    # 临时加入无法识别的代码，通过 --manual-ticker 确认后应被写入
    tickers_path = settings.project_root / "config" / "tickers.yaml"
    original = tickers_path.read_text(encoding="utf-8")
    try:
        import yaml

        config = yaml.safe_load(original) or {}
        config["watchlist"].append({"ticker": "UNKNOWN", "name": "未知"})
        tickers_path.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")

        data = _run(
            "update",
            "securities",
            "--manual-ticker",
            "UNKNOWN:SZ:手动标的:stock",
        )
        assert data["success"] is True
        web_json = settings.project_root / "web" / "public" / "security-master.json"
        loaded = json.loads(web_json.read_text(encoding="utf-8"))
        assert any(item["ticker"] == "UNKNOWN.SZ" for item in loaded)
    finally:
        tickers_path.write_text(original, encoding="utf-8")


def test_update_securities_dry_run_does_not_write_file() -> None:
    import pandas as pd

    # 先正常写入，获取路径
    data = _run("update", "securities")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    mtime_before = snapshot_path.stat().st_mtime

    # dry-run 不应更新文件
    dry = _run("update", "securities", "--dry-run")
    assert dry["success"] is True
    assert "snapshot_path" not in dry
    assert snapshot_path.stat().st_mtime == mtime_before


def test_update_securities_version_matches_parquet() -> None:
    data = _run("update", "securities")
    assert data["success"] is True
    version = data["version"]
    df = pd.read_parquet(Path(data["snapshot_path"]))
    assert (df["version"] == version).all()


def test_update_securities_reports_unrecognized_for_confirmation() -> None:
    # 临时修改 tickers.yaml，加入无法识别的代码
    tickers_path = settings.project_root / "config" / "tickers.yaml"
    original = tickers_path.read_text(encoding="utf-8")
    try:
        import yaml

        config = yaml.safe_load(original) or {}
        config["watchlist"].append({"ticker": "NOTATICKER", "name": "未知"})
        tickers_path.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")

        result = subprocess.run(
            [PYTHON, "-m", "src.cli.main", "--format", "json", "update", "securities"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        data = json.loads(result.stdout)
        assert data["success"] is False
        assert data.get("needs_confirmation") is True
        assert "NOTATICKER" in data.get("unrecognized_tickers", [])
    finally:
        tickers_path.write_text(original, encoding="utf-8")


def test_update_monthly_generates_capital_flow_and_macro_report_snapshots() -> None:
    data = _run("update", "monthly", "--mock")
    assert data["success"] is True
    snapshots = {s["report_type"]: s for s in data["snapshots"]}
    assert "capital_flow" in snapshots
    assert "macro_report" in snapshots

    cf_path = Path(snapshots["capital_flow"]["snapshot_path"])
    cf = read_snapshot(cf_path, CapitalFlowSnapshot)
    assert cf.report_type == "capital_flow"
    assert cf.report_month
    assert len(cf.indicators) >= 4

    categories = {ind.category for ind in cf.indicators}
    assert categories == {"growth", "inflation", "liquidity", "market_structure"}

    for ind in cf.indicators:
        assert ind.metadata.source
        assert ind.metadata.retrieved_at is not None
        assert ind.metadata.tier is not None

    assert len(cf.assessments) == 4
    assert {a.question_id for a in cf.assessments} == {"Q1", "Q2", "Q3", "Q4"}
    for a in cf.assessments:
        assert a.label in {"overheated", "neutral", "cool"}

    macro_path = Path(snapshots["macro_report"]["snapshot_path"])
    macro = read_snapshot(macro_path, MacroReportSnapshot)
    assert macro.report_type == "macro_report"
    assert macro.summary
    assert len(macro.four_questions) == 4
    assert macro.capital_flow_snapshot_id == cf.snapshot_id

    web_json = settings.project_root / "web" / "public" / "macro-report.json"
    assert web_json.exists()
    loaded = json.loads(web_json.read_text(encoding="utf-8"))
    assert "report_month" in loaded
    assert len(loaded["indicators"]) >= 4
    assert "four_questions" in loaded
    assert loaded["authority_tier"] is not None


def test_analyze_macro_mock_generates_macro_report() -> None:
    data = _run("analyze", "macro", "--mock")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    report = read_snapshot(snapshot_path, MacroReportSnapshot)
    assert report.report_type == "macro_report"
    assert report.summary
    assert len(report.four_questions) == 4
    assert report.capital_flow_snapshot_id
    assert report.outlook


def test_macro_report_web_json_exists_after_update() -> None:
    _run("update", "monthly", "--mock")
    web_json = settings.project_root / "web" / "public" / "macro-report.json"
    assert web_json.exists()
    loaded = json.loads(web_json.read_text(encoding="utf-8"))
    assert "growth_label" in loaded
    assert "inflation_label" in loaded
    assert "liquidity_label" in loaded
    assert "market_structure_label" in loaded
    assert loaded["report_month"]
