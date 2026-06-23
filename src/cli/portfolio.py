"""持仓管理 CLI。"""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.analysis.portfolio_returns import (
    derive_position_lots,
    portfolio_summary,
)
from src.cli.formatting import format_result
from src.common.logger import get_logger
from src.common.models import PortfolioSnapshot, PositionLot, SourceMetadata, Transaction
from src.common.paths import get_data_dir
from src.common.snapshot_io import write_snapshot
from src.data_standardization.transaction_loader import (
    load_transactions,
    merge_with_existing,
    save_transactions,
)
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)

USER_TRANSACTIONS_PATH = get_data_dir("user") / "transactions.csv"
USER_CASH_PATH = get_data_dir("user") / "cash.json"


def _get_cash() -> Decimal:
    """读取用户当前现金余额；未配置时返回 0。"""
    if not USER_CASH_PATH.exists():
        return Decimal("0")
    try:
        data = json.loads(USER_CASH_PATH.read_text(encoding="utf-8"))
        return Decimal(str(data.get("cash", "0")))
    except Exception:
        return Decimal("0")


def _load_transactions(tx_path: Path | None = None) -> list[Transaction]:
    """加载本地交易流水；文件不存在时返回空列表。"""
    path = tx_path or USER_TRANSACTIONS_PATH
    if not path.exists():
        return []
    return load_transactions(path, raw_source=str(path))


def build_portfolio_snapshot(
    transactions: list[Transaction],
    cash: Decimal | None = None,
    trade_date: date | None = None,
) -> PortfolioSnapshot:
    """由交易流水生成 ``PortfolioSnapshot``。"""
    if cash is None:
        cash = _get_cash()

    positions, realized_pnl = derive_position_lots(transactions)
    summary = portfolio_summary(positions, realized_pnl, cash)

    version_inputs = [p.model_dump() for p in positions] + [str(cash)]
    version = generate_version(version_inputs)

    return PortfolioSnapshot(
        snapshot_id=f"portfolio-{version}",
        version=version,
        account="default",
        trade_date=trade_date or date.today(),
        cash=summary["cash"],
        total_assets=summary["total_assets"],
        total_market_value=summary["total_market_value"],
        unrealized_pnl=summary["unrealized_pnl"],
        realized_pnl=summary["realized_pnl"],
        positions=positions,
        sector_exposure=summary["sector_exposure"],
        metadata=SourceMetadata(
            source="climbing.portfolio",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )


def _write_web_portfolio_summary(snapshot: PortfolioSnapshot) -> Path:
    """将最新 portfolio 摘要写入 web/public，供前端静态读取。"""
    web_public = Path(__file__).resolve().parents[2] / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "portfolio-summary.json"
    summary = {
        "last_snapshot_at": snapshot.created_at.isoformat(),
        "version": snapshot.version,
        "cash": str(snapshot.cash),
        "total_assets": str(snapshot.total_assets),
        "total_market_value": str(snapshot.total_market_value),
        "unrealized_pnl": str(snapshot.unrealized_pnl),
        "realized_pnl": str(snapshot.realized_pnl),
        "sector_exposure": [
            {"category": e.category, "value_pct": str(e.value_pct)}
            for e in snapshot.sector_exposure
        ],
        "positions": [
            {
                "ticker": p.ticker,
                "quantity": p.quantity,
                "cost_basis": str(p.cost_basis),
                "market_price": str(p.market_price) if p.market_price is not None else None,
                "market_value": str(p.market_value) if p.market_value is not None else None,
                "unrealized_pnl": str(p.unrealized_pnl) if p.unrealized_pnl is not None else None,
                "realized_pnl": str(p.realized_pnl),
                "account": p.account,
            }
            for p in snapshot.positions
        ],
    }
    web_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote portfolio summary for web -> %s", web_path)
    return web_path


def _derive_positions(csv_path: Path) -> list[PositionLot]:
    """兼容旧入口：从交易流水 CSV 推导当前持仓。"""
    transactions = _load_transactions(csv_path)
    positions, _ = derive_position_lots(transactions)
    return positions


@app.command("summary")
def summary(ctx: typer.Context) -> None:
    """显示当前持仓摘要并生成快照。"""
    logger.info("Showing portfolio summary")
    transactions = _load_transactions()
    snapshot = build_portfolio_snapshot(transactions)
    path = write_snapshot(snapshot, "portfolio")
    _write_web_portfolio_summary(snapshot)
    format_result(
        ctx,
        success=True,
        message=f"持仓摘要：{len(snapshot.positions)} 只标的。",
        snapshot_path=path,
        version=snapshot.version,
    )


@app.command("import")
def import_positions(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="持仓 CSV 文件路径"),
) -> None:
    """从 CSV 导入持仓（占位，保留以兼容旧接口）。"""
    logger.info("Importing positions from %s", file)
    format_result(
        ctx,
        success=True,
        message=f"持仓导入完成（占位）：{file}",
    )


def _import_transactions_impl(
    ctx: typer.Context,
    file: str,
    append: bool,
) -> None:
    """交易流水导入公共实现。"""
    src = Path(file)
    if not src.exists():
        format_result(
            ctx,
            success=False,
            message=f"文件不存在：{file}",
        )
        raise typer.Exit(code=1)

    new_transactions = load_transactions(src, raw_source=str(src))

    if append:
        merged = merge_with_existing(new_transactions, USER_TRANSACTIONS_PATH)
    else:
        merged = new_transactions

    save_transactions(merged, USER_TRANSACTIONS_PATH)
    logger.info("Saved %d transactions -> %s", len(merged), USER_TRANSACTIONS_PATH)

    snapshot = build_portfolio_snapshot(merged)
    path = write_snapshot(snapshot, "portfolio")
    _write_web_portfolio_summary(snapshot)

    format_result(
        ctx,
        success=True,
        message=f"交易流水导入完成：{len(snapshot.positions)} 只标的",
        snapshot_path=path,
        version=snapshot.version,
    )


@app.command("import-transactions")
def import_transactions(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="交易流水 CSV/TSV 文件路径"),
    append: bool = typer.Option(
        True,
        "--append/--overwrite",
        help="是否与已有流水合并去重（默认合并）；--overwrite 会覆盖。",
    ),
) -> None:
    """从 CSV/TSV 导入交易流水并刷新持仓快照。"""
    _import_transactions_impl(ctx, file, append=append)


@app.command("transactions")
def transactions_legacy(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="交易流水 CSV/TSV 文件路径"),
) -> None:
    """``import-transactions`` 的别名，保持向后兼容。"""
    _import_transactions_impl(ctx, file, append=True)
