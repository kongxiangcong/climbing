"""持仓管理 CLI。"""

import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.common.logger import get_logger
from src.common.models import Exposure, PortfolioSnapshot, PositionLot, SourceMetadata
from src.common.paths import get_data_dir
from src.common.snapshot_io import write_snapshot
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)


def _derive_positions(csv_path: Path) -> list[PositionLot]:
    """从交易流水 CSV 推导当前持仓（Slice 1：简化平均成本法）。"""
    import csv

    lots: dict[str, dict[str, Any]] = {}
    with csv_path.open("r", encoding="utf-8-sig") as f:
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
                lots[ticker]["qty"] -= qty
                if lots[ticker]["qty"] <= 0:
                    del lots[ticker]

    positions = []
    for ticker, lot in lots.items():
        if lot["qty"] > 0:
            positions.append(
                PositionLot(
                    ticker=ticker,
                    quantity=lot["qty"],
                    cost_basis=lot["cost"] / lot["qty"],
                )
            )
    return positions


def _build_portfolio_snapshot(positions: list[PositionLot]) -> PortfolioSnapshot:
    total_market_value = Decimal("0") + sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    version = generate_version([p.model_dump() for p in positions])
    return PortfolioSnapshot(
        snapshot_id=f"portfolio-{version}",
        version=version,
        trade_date=date.today(),
        positions=positions,
        total_market_value=total_market_value,
        total_assets=total_market_value,
        sector_exposure=[Exposure(category="unknown", value_pct=Decimal("100"))],
        metadata=SourceMetadata(
            source="climbing.portfolio.import_transactions",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """显示当前持仓摘要并生成快照。"""
    logger.info("Showing portfolio summary")
    tx_path = get_data_dir("user") / "transactions.csv"
    positions = _derive_positions(tx_path) if tx_path.exists() else []
    snapshot = _build_portfolio_snapshot(positions)
    path = write_snapshot(snapshot, "portfolio")
    format_result(
        ctx,
        success=True,
        message=f"持仓摘要：{len(positions)} 只标的。",
        snapshot_path=path,
        version=snapshot.version,
    )


@app.command("import")
def import_positions(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="持仓 CSV 文件路径"),
) -> None:
    """从 CSV 导入持仓。"""
    logger.info("Importing positions from %s", file)
    format_result(
        ctx,
        success=True,
        message=f"持仓导入完成（占位）：{file}",
    )


@app.command("transactions")
def import_transactions(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="交易流水 CSV 文件路径"),
) -> None:
    """从 CSV 导入交易流水并刷新持仓快照。"""
    src = Path(file)
    if not src.exists():
        format_result(
            ctx,
            success=False,
            message=f"文件不存在：{file}",
        )
        raise typer.Exit(code=1)

    dst = get_data_dir("user") / "transactions.csv"
    shutil.copy2(src, dst)
    logger.info("Copied transactions %s -> %s", src, dst)

    positions = _derive_positions(dst)
    snapshot = _build_portfolio_snapshot(positions)
    path = write_snapshot(snapshot, "portfolio")
    format_result(
        ctx,
        success=True,
        message=f"交易流水导入完成：{len(positions)} 只标的",
        snapshot_path=path,
        version=snapshot.version,
    )
