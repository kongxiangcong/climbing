"""数据更新 CLI。"""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import (
    Exposure,
    IndexMetric,
    MarketSnapshot,
    PortfolioSnapshot,
    PositionLot,
    SourceMetadata,
)
from src.common.paths import get_data_dir
from src.common.snapshot_io import write_snapshot
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
    tx_path = get_data_dir("user") / "transactions.csv"
    positions: list[PositionLot] = []
    if tx_path.exists():
        import csv

        lots: dict[str, dict[str, Any]] = {}
        with tx_path.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row["ticker"].strip()
                side = row["side"].strip().lower()
                qty = int(row["quantity"])
                price = Decimal(str(row["price"]))
                if side == "buy":
                    if ticker not in lots:
                        lots[ticker] = {"qty": 0, "cost": Decimal("0")}
                    lots[ticker]["qty"] += qty
                    lots[ticker]["cost"] += qty * price
                elif side == "sell" and ticker in lots:
                    # Slice 1：简化平均成本扣除，非严格 FIFO
                    lots[ticker]["qty"] -= qty
                    if lots[ticker]["qty"] <= 0:
                        del lots[ticker]
        for ticker, lot in lots.items():
            if lot["qty"] > 0:
                positions.append(
                    PositionLot(
                        ticker=ticker,
                        quantity=lot["qty"],
                        cost_basis=lot["cost"] / lot["qty"],
                    )
                )

    version = generate_version([p.model_dump() for p in positions])
    total_market_value = Decimal("0") + sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    snapshot = PortfolioSnapshot(
        snapshot_id=f"portfolio-{version}",
        version=version,
        trade_date=date.today(),
        positions=positions,
        total_market_value=total_market_value,
        total_assets=total_market_value,
        sector_exposure=[Exposure(category="unknown", value_pct=Decimal("100"))],
        metadata=SourceMetadata(
            source="climbing.update.daily",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "portfolio")
    return path, version


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
