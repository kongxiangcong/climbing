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

    market = read_snapshot(Path(snapshots["market"]["snapshot_path"]), MarketSnapshot)
    assert market.report_type == "market"
    assert market.indices

    portfolio = read_snapshot(
        Path(snapshots["portfolio"]["snapshot_path"]), PortfolioSnapshot
    )
    assert portfolio.report_type == "portfolio"


def test_update_daily_review_generates_daily_review_snapshot() -> None:
    data = _run("update", "daily-review")
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    review = read_snapshot(snapshot_path, DailyReviewSnapshot)
    assert review.report_type == "daily_review"


def test_analyze_stock_generates_research_snapshot() -> None:
    ticker = "000725.SZ"
    data = _run("analyze", "stock", ticker)
    assert data["success"] is True
    snapshot_path = Path(data["snapshot_path"])
    research = read_snapshot(snapshot_path, ResearchSnapshot)
    assert research.report_type == "research"
    assert research.ticker == ticker


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
    create_data = _run("plan", "create", "000725.SZ", "--name", "integration-test-plan")
    assert create_data["success"] is True
    plan_id = create_data["plan_id"]
    plan_path = Path(create_data["snapshot_path"])
    plan = TradePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    assert plan.ticker == "000725.SZ"

    check_data = _run("plan", "check", plan_id)
    assert check_data["success"] is True
    review_path = Path(check_data["snapshot_path"])
    review = read_snapshot(review_path, PlanReviewSnapshot)
    assert review.report_type == "plan_review"
    assert review.plan_id == plan_id


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
