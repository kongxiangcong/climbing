"""宏观月报 Markdown 生成器。"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.common.config import settings
from src.common.models import CapitalFlowSnapshot, MacroReportSnapshot


class CapitalFlowReportGenerator:
    """基于 CapitalFlowSnapshot / MacroReportSnapshot 生成 Markdown 月报。"""

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = (
                settings.project_root / "src" / "report_generation" / "templates"
            )
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,
        )

    def generate(
        self,
        capital_flow: CapitalFlowSnapshot,
        macro_report: MacroReportSnapshot | None = None,
    ) -> str:
        """渲染 markdown 字符串。"""
        template = self.env.get_template("capital_flow_report.md.j2")
        return template.render(
            report_month=capital_flow.report_month,
            version=capital_flow.version,
            created_at=capital_flow.created_at,
            indicators=capital_flow.indicators,
            assessments=capital_flow.assessments,
            growth_label=capital_flow.growth_label,
            inflation_label=capital_flow.inflation_label,
            liquidity_label=capital_flow.liquidity_label,
            market_structure_label=capital_flow.market_structure_label,
            macro_report=macro_report,
        )
