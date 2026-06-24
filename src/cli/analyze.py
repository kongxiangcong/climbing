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
    get_equity_report_dir,
    write_equity_report_files,
)
from src.common.equity_researcher_adapter import build_research_snapshot_from_skill_output
from src.common.logger import get_logger
from src.common.models import (
    CapitalFlowAssessment,
    CapitalFlowSnapshot,
    MacroReportSnapshot,
    ResearchSnapshot,
    SourceMetadata,
    Valuation,
)
from src.common.snapshot_io import latest_snapshot_path, read_snapshot, write_snapshot
from src.common.research_cache import CacheTier, ResearchCache
from src.common.skill_runner import run_skill
from src.common.snapshot_validator import SnapshotValidator
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


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _build_research_snapshot(
    ticker: str,
    version: str,
    fixture: dict[str, Any],
    skill_summary: str | None = None,
) -> ResearchSnapshot:
    """基于 fixture 与可选 skill 输出构造 ResearchSnapshot（后向兼容）。"""
    valuation_data = fixture.get("valuation", {}) or {}
    valuation = Valuation(
        method=valuation_data.get("method", "unknown"),
        value_low=_to_decimal(valuation_data.get("value_low")),
        value_high=_to_decimal(valuation_data.get("value_high")),
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
        target_price_low=_to_decimal(fixture.get("target_price_low")),
        target_price_high=_to_decimal(fixture.get("target_price_high")),
        pdf_path=None,
        references=fixture.get("references", []),
        metadata=SourceMetadata(
            source="climbing.analyze.stock",
            retrieved_at=datetime.now(),
            version="1.0.0",
        ),
    )


def _build_minor_refresh_snapshot(
    existing: ResearchSnapshot,
    ticker: str,
    version: str,
    fixture: dict[str, Any],
) -> ResearchSnapshot:
    """基于已有快照生成轻量数据刷新快照：更新版本、时间与价格/估值字段。"""
    data = existing.model_dump(mode="json")
    data["snapshot_id"] = f"research-{ticker}-{version}"
    data["version"] = version
    data["created_at"] = datetime.now().isoformat()
    data["metadata"] = {
        "source": "climbing.analyze.stock.minor_refresh",
        "retrieved_at": datetime.now().isoformat(),
        "version": "1.0.0",
    }

    # 用 fixture 中的价格/估值覆盖（如有）
    if "stock_price_data" in fixture:
        data["stock_price_data"] = fixture["stock_price_data"]
    if "valuation_data" in fixture:
        data["valuation_data"] = fixture["valuation_data"]
    if "valuation" in fixture:
        data["valuation"] = fixture["valuation"]
    if "target_price_low" in fixture:
        data["target_price_low"] = fixture["target_price_low"]
    if "target_price_high" in fixture:
        data["target_price_high"] = fixture["target_price_high"]

    # 标记为 minor refresh
    data["summary"] = f"{data.get('summary', '')}\n[minor data refresh]".strip()

    return ResearchSnapshot.model_validate(data)


def _copy_snapshot_for_web(report_dir: Path, ticker: str) -> Path | None:
    """将最新 snapshot.json 复制到 web/public，供前端静态回退读取。"""
    from src.common.config import settings

    snapshot_src = report_dir / "snapshot.json"
    if not snapshot_src.exists():
        return None
    web_dir = settings.project_root / "web" / "public" / "reports" / "equity" / ticker
    web_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dst = web_dir / "snapshot.json"
    shutil.copy2(snapshot_src, snapshot_dst)
    return snapshot_dst


def _write_report(
    ctx: typer.Context,
    ticker: str,
    snapshot: ResearchSnapshot,
    report_dir: Path,
) -> None:
    """生成 PDF、运行校验、写入四个标准文件并同步到 web/public。"""
    generator = EquityReportGenerator()
    report_data = generator.generate_report_data(snapshot.model_dump(mode="json"))
    html_path = report_dir / "report.html"
    pdf_path = report_dir / "report.pdf"
    generator.generate_html(ticker, report_data, html_path)
    generator.generate_pdf(html_path, pdf_path)

    snapshot.pdf_path = str(pdf_path)

    validator = SnapshotValidator(snapshot)
    validator.run_all()
    qa_check = validator.to_dict()
    if not qa_check["checks_passed"]:
        logger.warning(
            "Snapshot validation issues for %s: %s",
            ticker,
            qa_check["issues"],
        )

    references = snapshot.references or []
    write_equity_report_files(
        report_dir=report_dir,
        snapshot=snapshot.model_dump(mode="json"),
        qa_check=qa_check,
        references=references,
        pdf_path=pdf_path,
    )

    web_path = _copy_snapshot_for_web(report_dir, ticker)
    if web_path:
        logger.info("Copied snapshot to web fallback: %s", web_path)

    format_result(
        ctx,
        success=True,
        message=f"个股研报快照生成完成：{ticker}",
        snapshot_path=report_dir / "snapshot.json",
        version=snapshot.version,
        extra={"report_dir": str(report_dir), "checks_passed": qa_check["checks_passed"]},
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
    force: bool = typer.Option(
        False,
        "--force",
        help="强制重新生成完整研报，忽略缓存",
    ),
    refresh_only: bool = typer.Option(
        False,
        "--refresh-only",
        help="仅在 minor_refresh 层级执行轻量数据刷新",
    ),
) -> None:
    """生成个股研报快照，带三级缓存逻辑。"""
    logger.info("Analyzing stock: %s (mock=%s, force=%s)", ticker, mock, force)

    if not mock and shutil.which("kimi") is None:
        logger.warning("Kimi CLI not found, falling back to mock mode")
        mock = True

    cache = ResearchCache(ticker)
    tier, existing_snapshot = cache.determine_tier()

    if force and refresh_only:
        format_result(
            ctx,
            success=False,
            message="--force 与 --refresh-only 不能同时使用",
        )
        raise typer.Exit(code=1)

    if not force and tier == CacheTier.FRESH:
        latest_path = cache.latest_snapshot_path()
        format_result(
            ctx,
            success=True,
            message=f"研报已是最新，直接返回缓存：{ticker}",
            snapshot_path=latest_path,
            version=existing_snapshot.version if existing_snapshot else None,
        )
        return

    if refresh_only and tier != CacheTier.MINOR_REFRESH:
        format_result(
            ctx,
            success=False,
            message="--refresh-only 仅在 minor_refresh 层级可用",
        )
        raise typer.Exit(code=1)

    version = generate_version(f"{ticker}-{datetime.now().isoformat()}")
    report_dir = get_equity_report_dir(ticker, version)

    if not force and tier == CacheTier.MINOR_REFRESH:
        logger.info("Performing minor refresh for %s", ticker)
        assert existing_snapshot is not None, "MINOR_REFRESH tier must have existing snapshot"
        fixture = _load_fixture("research_snapshot_full.json")
        snapshot = _build_minor_refresh_snapshot(
            existing=existing_snapshot,
            ticker=ticker,
            version=version,
            fixture=fixture,
        )
        _write_report(ctx, ticker, snapshot, report_dir)
        return

    # Full research path: NON_EXISTENT / STALE / force
    full_fixture = _load_fixture("research_snapshot_full.json")
    skill_output: dict[str, Any] | None = None
    skill_summary: str | None = None

    if mock:
        skill_output = full_fixture
    else:
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
            try:
                skill_output = json.loads(stdout)
            except json.JSONDecodeError:
                # 非 JSON 输出时作为 summary 补充，后续走 fixture 兜底
                skill_summary = stdout.strip()[:2000]

    if skill_output is not None:
        snapshot = build_research_snapshot_from_skill_output(
            ticker=ticker,
            version=version,
            skill_output=skill_output,
            source="skills/stock-research",
        )
    else:
        legacy_fixture = _load_fixture("research_snapshot.json")
        snapshot = _build_research_snapshot(
            ticker, version, legacy_fixture, skill_summary
        )

    _write_report(ctx, ticker, snapshot, report_dir)


def _load_or_build_capital_flow_snapshot(
    report_month: str | None,
) -> tuple[Path, CapitalFlowSnapshot]:
    """优先复用已存在的 CapitalFlowSnapshot，否则重新生成。"""
    from src.cli.update import _capital_flow_snapshot

    if report_month:
        return _capital_flow_snapshot(report_month)

    latest = latest_snapshot_path("capital_flow")
    if latest is not None:
        snapshot = read_snapshot(latest, CapitalFlowSnapshot)
        return latest, snapshot

    return _capital_flow_snapshot()


@app.command("macro")
def analyze_macro(
    ctx: typer.Context,
    mock: bool = typer.Option(
        False,
        "--mock",
        help="使用 mock skill 输出（测试用，不调用真实 Kimi CLI）",
        envvar="CLIMBING_MOCK_SKILL",
    ),
    report_month: str | None = typer.Option(
        None,
        "--month",
        help="报告月份，格式 YYYY-MM；默认复用最新事实快照",
    ),
) -> None:
    """生成宏观月报叙事快照。"""
    logger.info("Analyzing macro (mock=%s, month=%s)", mock, report_month)

    if not mock and shutil.which("kimi") is None:
        logger.warning("Kimi CLI not found, falling back to mock mode")
        mock = True

    try:
        cf_path, cf_snapshot = _load_or_build_capital_flow_snapshot(report_month)
    except Exception as exc:
        logger.error("Capital flow snapshot load/build failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"宏观事实表准备失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    try:
        from src.cli.update import _macro_report_snapshot, _write_macro_report_web_summary

        macro_path, macro_version = _macro_report_snapshot(cf_snapshot, mock=mock)
        _write_macro_report_web_summary(cf_snapshot)
    except Exception as exc:
        logger.error("Macro report generation failed: %s", exc)
        format_result(
            ctx,
            success=False,
            message=f"宏观月报生成失败：{exc}",
        )
        raise typer.Exit(code=1) from exc

    format_result(
        ctx,
        success=True,
        message=f"宏观月报生成完成：{cf_snapshot.report_month}",
        snapshot_path=macro_path,
        version=macro_version,
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
