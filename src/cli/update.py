"""数据更新 CLI。"""

import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.cli.portfolio import build_portfolio_snapshot
from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import (
    IndexMetric,
    MarketSnapshot,
    SourceMetadata,
)
from src.common.paths import get_data_dir
from src.common.snapshot_io import write_snapshot
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


def _market_snapshot() -> tuple[Path, str]:
    """生成市场事实快照。"""
    fixture = _load_fixture("market_snapshot.json")
    version = generate_version(fixture)
    trade_date = datetime.strptime(
        fixture.get("trade_date", datetime.now().strftime("%Y-%m-%d")),
        "%Y-%m-%d",
    ).date()

    indices = [
        IndexMetric(
            ticker=m["ticker"],
            name=m["name"],
            close=Decimal(str(m["close"])),
            change_pct=Decimal(str(m.get("change_pct", 0))),
            volume=m.get("volume"),
        )
        for m in fixture.get("indices", [])
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

    snapshot = MarketSnapshot(
        snapshot_id=f"market-{version}",
        version=version,
        trade_date=trade_date,
        indices=indices,
        breadth=fixture.get("breadth", {"advancers": 0, "decliners": 0, "unchanged": 0}),
        total_turnover=Decimal(str(fixture.get("total_turnover", 0))),
        sector_heat=fixture.get("sector_heat", []),
        margin_balance=Decimal(str(fixture.get("margin_balance", 0))) if "margin_balance" in fixture else None,
        northbound_flow=Decimal(str(fixture.get("northbound_flow", 0))) if "northbound_flow" in fixture else None,
        etf_flow={k: Decimal(str(v)) for k, v in fixture.get("etf_flow", {}).items()},
        sentiment_score=fixture.get("sentiment_score"),
        risk_appetite=fixture.get("risk_appetite"),
        metadata=SourceMetadata(
            source="climbing.update.daily",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "market")
    return path, version


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
def daily_update(ctx: typer.Context) -> None:
    """收盘后一键更新：市场事实、持仓事实。"""
    logger.info("Starting daily update")
    market_path, market_version = _market_snapshot()
    portfolio_path, portfolio_version = _portfolio_snapshot()
    snapshots: list[dict[str, Any]] = [
        {"report_type": "market", "snapshot_path": str(market_path), "version": market_version},
        {"report_type": "portfolio", "snapshot_path": str(portfolio_path), "version": portfolio_version},
    ]
    _write_system_status(snapshots)
    format_result(
        ctx,
        success=True,
        message="Daily update completed.",
        extra={"snapshots": snapshots},
    )


@app.command("monthly")
def monthly_update(ctx: typer.Context) -> None:
    """月更任务：宏观报告、市场温度。"""
    tasks = settings.get("update_schedule.monthly.tasks", [])
    logger.info("Starting monthly update: %s", tasks)
    for task in tasks:
        logger.info("Executing task: %s", task)
    format_result(
        ctx,
        success=True,
        message="Monthly update completed (placeholder).",
        extra={"tasks": tasks},
    )


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
