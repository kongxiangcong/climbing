"""分析 CLI。"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.common.logger import get_logger
from src.common.models import ResearchSnapshot, SourceMetadata, Valuation
from src.common.snapshot_io import write_snapshot
from src.data_standardization.versioner import generate_version

app = typer.Typer()
logger = get_logger(__name__)


def _load_fixture(name: str) -> dict[str, Any]:
    from src.common.config import settings

    path = settings.project_root / "tests" / "fixtures" / name
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


@app.command("stock")
def analyze_stock(
    ctx: typer.Context,
    ticker: str = typer.Argument(..., help="股票代码，如 000725.SZ"),
) -> None:
    """生成个股研报快照。"""
    logger.info("Analyzing stock: %s", ticker)

    fixture = _load_fixture(f"research_{ticker.replace('.', '_')}.json")
    if not fixture:
        fixture = _load_fixture("research_snapshot.json")

    version = generate_version(f"{ticker}-{fixture}")
    valuation = Valuation(
        method=fixture.get("valuation", {}).get("method", "unknown"),
        value_low=Decimal(str(fixture["valuation"]["value_low"])) if fixture.get("valuation", {}).get("value_low") else None,
        value_high=Decimal(str(fixture["valuation"]["value_high"])) if fixture.get("valuation", {}).get("value_high") else None,
        assumptions=fixture.get("valuation", {}).get("assumptions", []),
    )
    snapshot = ResearchSnapshot(
        snapshot_id=f"research-{ticker}-{version}",
        version=version,
        ticker=ticker,
        summary=fixture.get("summary", f"{ticker} 个股研报占位"),
        six_dimensions=fixture.get("six_dimensions", {}),
        valuation=valuation,
        risks=fixture.get("risks", []),
        assumptions=fixture.get("assumptions", []),
        invalidation_conditions=fixture.get("invalidation_conditions", []),
        target_price_low=Decimal(str(fixture["target_price_low"])) if fixture.get("target_price_low") else None,
        target_price_high=Decimal(str(fixture["target_price_high"])) if fixture.get("target_price_high") else None,
        pdf_path=fixture.get("pdf_path"),
        references=fixture.get("references", []),
        metadata=SourceMetadata(
            source="climbing.analyze.stock",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )
    path = write_snapshot(snapshot, "research", ticker)
    format_result(
        ctx,
        success=True,
        message=f"个股研报快照生成完成：{ticker}",
        snapshot_path=path,
        version=version,
    )


@app.command("portfolio")
def analyze_portfolio(ctx: typer.Context) -> None:
    """生成持仓组合分析报告。"""
    logger.info("Analyzing portfolio")
    format_result(
        ctx,
        success=True,
        message="组合分析报告生成完成（占位）。",
    )


@app.command("macro")
def analyze_macro(ctx: typer.Context) -> None:
    """生成市场与宏观月报。"""
    logger.info("Analyzing macro")
    format_result(
        ctx,
        success=True,
        message="宏观月报生成完成（占位）。",
    )
