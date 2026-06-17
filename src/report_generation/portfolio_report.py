"""持仓组合报告生成。"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.common.config import settings
from src.common.logger import get_logger
from src.data_standardization.versioner import generate_version, snapshot_path

logger = get_logger(__name__)


class PortfolioReportGenerator:
    """生成持仓组合报告。"""

    def __init__(self) -> None:
        template_dir = settings.project_root / "src" / "report_generation" / "templates"
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(
        self,
        positions: list[dict[str, Any]],
        risk_metrics: dict[str, Any],
        report_date: str | None = None,
    ) -> Path:
        report_date = report_date or datetime.now().strftime("%Y-%m-%d")
        version = generate_version(f"portfolio-{report_date}")

        template = self.env.get_template("portfolio_report.md.j2")
        content = template.render(
            report_date=report_date,
            version=version,
            positions=positions,
            risk=risk_metrics,
        )

        path = snapshot_path("portfolio", None, version)
        path.write_text(content, encoding="utf-8")
        logger.info("Generated portfolio report -> %s", path)
        return path
