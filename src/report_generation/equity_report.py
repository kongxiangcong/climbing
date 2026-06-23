"""个股深度研报 HTML/PDF 生成 helper。"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.common.config import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


class EquityReportGenerator:
    """基于 Jinja2 模板生成最小深度研报 HTML 与 PDF。"""

    def __init__(self) -> None:
        skill_root = settings.project_root / "skills" / "stock-research"
        self.template_dir = skill_root / "templates"
        self.css_path = skill_root / "output" / "report.css"
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

    def _read_css(self) -> str:
        """读取 skill CSS 文件内容。"""
        if self.css_path.exists():
            return self.css_path.read_text(encoding="utf-8")
        logger.warning("CSS file not found: %s", self.css_path)
        return ""

    def generate_html(
        self,
        ticker: str,
        report_data: dict[str, Any],
        output_path: Path,
    ) -> Path:
        """渲染 HTML 报告。"""
        template = self.env.get_template("report.html.j2")
        context: dict[str, Any] = {
            "ticker": ticker,
            "report_date": datetime.now().strftime("%Y-%m-%d"),
            "css_content": self._read_css(),
        }
        context.update(report_data)
        html = template.render(**context)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Generated HTML report for %s -> %s", ticker, output_path)
        return output_path

    def generate_pdf(self, html_path: Path, pdf_path: Path) -> Path:
        """将 HTML 转换为 PDF。

        优先使用 weasyprint；若不可用则生成占位 PDF。
        """
        try:
            from weasyprint import HTML  # type: ignore

            HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            logger.info("Generated PDF report -> %s", pdf_path)
            return pdf_path
        except ImportError:
            logger.warning(
                "weasyprint not installed; writing placeholder PDF to %s", pdf_path
            )
            from src.common.equity_report_io import _minimal_pdf_bytes

            pdf_path.write_bytes(_minimal_pdf_bytes())
            return pdf_path

    def generate_report_data(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """从 ResearchSnapshot dict 中提取模板所需变量。"""
        valuation = snapshot.get("valuation", {}) or {}
        return {
            "name": snapshot.get("ticker"),
            "title": snapshot.get("summary", "")[:30] or "个股深度研报",
            "rating": "HOLD",
            "summary": snapshot.get("summary", ""),
            "target_low": str(valuation.get("value_low")) if valuation.get("value_low") else None,
            "target_high": str(valuation.get("value_high")) if valuation.get("value_high") else None,
            "valuation_method": valuation.get("method"),
            "valuation_assumptions": valuation.get("assumptions", []),
            "six_dimensions": snapshot.get("six_dimensions", {}),
            "risks": snapshot.get("risks", []),
            "assumptions": snapshot.get("assumptions", []),
            "invalidation_conditions": snapshot.get("invalidation_conditions", []),
            "references": snapshot.get("references", []),
        }
