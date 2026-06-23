"""分析 CLI。"""

import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from src.cli.formatting import format_result
from src.common.equity_report_io import (
    build_qa_check,
    get_equity_report_dir,
    write_equity_report_files,
)
from src.common.logger import get_logger
from src.common.models import ResearchSnapshot, SourceMetadata, Valuation
from src.common.skill_runner import run_skill
from src.data_standardization.versioner import generate_version
from src.report_generation.equity_report import EquityReportGenerator

app = typer.Typer()
logger = get_logger(__name__)


def _load_fixture(name: str) -> dict[str, Any]:
    from src.common.config import settings

    path = settings.project_root / "tests" / "fixtures" / name
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return {}


def _build_research_snapshot(
    ticker: str,
    version: str,
    fixture: dict[str, Any],
    skill_summary: str | None = None,
) -> ResearchSnapshot:
    """基于 fixture 与可选 skill 输出构造 ResearchSnapshot。"""
    valuation_data = fixture.get("valuation", {}) or {}
    valuation = Valuation(
        method=valuation_data.get("method", "unknown"),
        value_low=(
            Decimal(str(valuation_data["value_low"]))
            if valuation_data.get("value_low") is not None
            else None
        ),
        value_high=(
            Decimal(str(valuation_data["value_high"]))
            if valuation_data.get("value_high") is not None
            else None
        ),
        assumptions=valuation_data.get("assumptions", []),
    )
    summary = skill_summary or fixture.get("summary", f"{ticker} 个股研报占位")
    return ResearchSnapshot(
        snapshot_id=f"research-{ticker}-{version}",
        version=version,
        ticker=ticker,
        summary=summary,
        six_dimensions=fixture.get("six_dimensions", {}),
        valuation=valuation,
        risks=fixture.get("risks", []),
        assumptions=fixture.get("assumptions", []),
        invalidation_conditions=fixture.get("invalidation_conditions", []),
        target_price_low=(
            Decimal(str(fixture["target_price_low"]))
            if fixture.get("target_price_low") is not None
            else None
        ),
        target_price_high=(
            Decimal(str(fixture["target_price_high"]))
            if fixture.get("target_price_high") is not None
            else None
        ),
        pdf_path=None,
        references=fixture.get("references", []),
        metadata=SourceMetadata(
            source="climbing.analyze.stock",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )


@app.command("stock")
def analyze_stock(
    ctx: typer.Context,
    ticker: str = typer.Argument(..., help="股票代码，如 000725.SZ"),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用，不调用真实 Kimi CLI）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
) -> None:
    """生成个股研报快照。"""
    logger.info("Analyzing stock: %s", ticker)

    if not mock and shutil.which("kimi") is None:
        logger.warning("Kimi CLI not found, falling back to mock mode")
        mock = True

    version = generate_version(f"{ticker}-{datetime.now().isoformat()}")
    report_dir = get_equity_report_dir(ticker, version)

    fixture = _load_fixture("research_snapshot.json")
    skill_summary: str | None = None

    if not mock:
        result = run_skill(
            prompt=f"请生成 {ticker} 的深度研报",
            skill_name="stock-research",
            output_dir=report_dir,
            timeout=300,
        )
        if not result.get("success"):
            format_result(
                ctx,
                success=False,
                message=f"Skill 调用失败: {result.get('stderr', 'unknown error')}",
            )
            raise typer.Exit(code=1)

        stdout = result.get("stdout", "") or ""
        if stdout.strip():
            # 骨架阶段仅将 skill 文本输出作为 summary 补充
            skill_summary = stdout.strip()[:2000]

    snapshot = _build_research_snapshot(ticker, version, fixture, skill_summary)

    # 生成 PDF
    generator = EquityReportGenerator()
    report_data = generator.generate_report_data(snapshot.model_dump(mode="json"))
    html_path = report_dir / "report.html"
    pdf_path = report_dir / "report.pdf"
    generator.generate_html(ticker, report_data, html_path)
    generator.generate_pdf(html_path, pdf_path)

    snapshot.pdf_path = str(pdf_path)

    qa_check = build_qa_check()
    references = snapshot.references or []
    write_equity_report_files(
        report_dir=report_dir,
        snapshot=snapshot.model_dump(mode="json"),
        qa_check=qa_check,
        references=references,
        pdf_path=pdf_path,
    )

    format_result(
        ctx,
        success=True,
        message=f"个股研报快照生成完成：{ticker}",
        snapshot_path=report_dir / "snapshot.json",
        version=version,
        extra={"report_dir": str(report_dir)},
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
