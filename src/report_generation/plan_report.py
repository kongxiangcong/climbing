"""交易计划报告生成。"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import TradePlan
from src.data_standardization.versioner import generate_version, snapshot_path

logger = get_logger(__name__)


class PlanReportGenerator:
    """生成交易计划跟踪报告。"""

    def __init__(self) -> None:
        template_dir = settings.project_root / "src" / "report_generation" / "templates"
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(
        self,
        plan: TradePlan,
        deviation: dict[str, Any],
        latest_price: float,
        report_date: str | None = None,
    ) -> Path:
        report_date = report_date or datetime.now().strftime("%Y-%m-%d")
        version = generate_version(f"{plan.plan_id}-{report_date}")

        template = self.env.get_template("plan_report.md.j2")
        content = template.render(
            report_date=report_date,
            version=version,
            plan=plan,
            deviation=deviation,
            latest_price=latest_price,
        )

        path = snapshot_path("plan", plan.ticker, version)
        path.write_text(content, encoding="utf-8")
        logger.info("Generated plan report for %s -> %s", plan.ticker, path)
        return path
