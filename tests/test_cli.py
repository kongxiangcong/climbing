"""CLI worker 集成测试：验证命令生成的 snapshot 符合 schema。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.common.config import settings
from src.common.models import (
    DailyReviewSnapshot,
    MarketSnapshot,
    PlanReviewSnapshot,
    PortfolioSnapshot,
    ResearchSnapshot,
    TradePlan,
)
from src.common.snapshot_io import read_snapshot

PROJECT_ROOT = settings.project_root
PYTHON = shutil.which("python") or "python"


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


def test_update_daily_generates_market_and_portfolio_snapshots() -> None:
    data = _run("update", "daily")
    assert data["success"] is True
    snapshots = {s["report_type"]: s for s in data["snapshots"]}
    assert "market" in snapshots
    assert "portfolio" in snapshots

    # 命令输出为 JSON，包含两个 snapshot 的路径和版本
    market_info = snapshots["market"]
    portfolio_info = snapshots["portfolio"]
    assert "snapshot_path" in market_info
    assert "version" in market_info
    assert "snapshot_path" in portfolio_info
    assert "version" in portfolio_info

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


def test_version_returns_json() -> None:
    data = _run("version")
    assert "version" in data


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
