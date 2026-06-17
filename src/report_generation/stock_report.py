"""个股分析报告生成。"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from src.common.config import settings
from src.common.logger import get_logger
from src.common.paths import get_project_root
from src.data_standardization.versioner import generate_version, snapshot_path

logger = get_logger(__name__)


class StockReportGenerator:
    """生成个股全景分析报告。"""

    def __init__(self) -> None:
        template_dir = settings.project_root / "src" / "report_generation" / "templates"
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(
        self,
        ticker: str,
        security_info: dict[str, Any],
        score_result: dict[str, Any],
        valuation: dict[str, Any],
        latest_price: float,
        report_date: str | None = None,
    ) -> Path:
        """生成 Markdown 报告并保存快照。"""
        report_date = report_date or datetime.now().strftime("%Y-%m-%d")
        version = generate_version(f"{ticker}-{report_date}")

        template = self.env.get_template("stock_report.md.j2")
        content = template.render(
            ticker=ticker,
            report_date=report_date,
            version=version,
            security_info=security_info,
            score=score_result,
            valuation=valuation,
            latest_price=latest_price,
        )

        path = snapshot_path("stock", ticker, version)
        path.write_text(content, encoding="utf-8")
        logger.info("Generated stock report for %s -> %s", ticker, path)
        return path
