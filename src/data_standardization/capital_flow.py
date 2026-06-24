"""宏观资金流事实表标准化。

当前以 fixture 数据为主，后续可扩展为读取本地 CSV、akshare、同花顺导出等真实数据源。
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from src.common.config import settings
from src.common.models import (
    CapitalFlowAssessment,
    CapitalFlowSnapshot,
    MacroIndicator,
    SourceMetadata,
)
from src.data_standardization.versioner import generate_version


class CapitalFlowStandardizer:
    """把原始宏观数据整理为符合 schema 的 CapitalFlowSnapshot。"""

    DEFAULT_FIXTURE = settings.project_root / "tests" / "fixtures" / "capital_flow.json"

    def __init__(self, fixture_path: Path | str | None = None) -> None:
        self.fixture_path = Path(fixture_path) if fixture_path else self.DEFAULT_FIXTURE

    def from_fixture(self) -> dict[str, Any]:
        """加载 fixture JSON；缺失时返回空结构。"""
        if not self.fixture_path.exists():
            return {
                "report_month": self._default_report_month(),
                "indicators": [],
                "assessments": [],
            }
        raw: dict[str, Any] = __import__("json").loads(
            self.fixture_path.read_text(encoding="utf-8")
        )
        return raw

    @staticmethod
    def _default_report_month() -> str:
        today = datetime.now()
        first_day = today.replace(day=1)
        prev_month = first_day - timedelta(days=1)
        return prev_month.strftime("%Y-%m")

    def build_snapshot(self, report_month: str | None = None) -> CapitalFlowSnapshot:
        """基于 fixture 构建 CapitalFlowSnapshot。"""
        data = self.from_fixture()
        month = report_month or data.get("report_month") or self._default_report_month()

        indicators = [
            MacroIndicator.model_validate(ind) for ind in data.get("indicators", [])
        ]
        assessments = [
            CapitalFlowAssessment.model_validate(a) for a in data.get("assessments", [])
        ]

        labels = self._derive_labels(indicators, data)

        if len(assessments) != 4:
            assessments = self._default_assessments(labels)

        version_data = {
            "report_month": month,
            "indicators": [ind.model_dump(mode="json") for ind in indicators],
            "assessments": [a.model_dump(mode="json") for a in assessments],
            "indicator_history": data.get("indicator_history", []),
            **labels,
        }
        version = generate_version(version_data)

        return CapitalFlowSnapshot(
            snapshot_id=f"capital-flow-{version}",
            version=version,
            report_month=month,
            indicators=indicators,
            assessments=assessments,
            metadata=SourceMetadata(
                source="climbing.capital_flow.fixture",
                retrieved_at=datetime.now(),
                version="1.0.0",
                tier=1,
                notes="Source: tests/fixtures/capital_flow.json",
            ),
            growth_label=cast(
                Literal["overheated", "neutral", "cool"], labels["growth_label"]
            ),
            inflation_label=cast(
                Literal["overheated", "neutral", "cool"], labels["inflation_label"]
            ),
            liquidity_label=cast(
                Literal["overheated", "neutral", "cool"], labels["liquidity_label"]
            ),
            market_structure_label=cast(
                Literal["overheated", "neutral", "cool"], labels["market_structure_label"]
            ),
            indicator_history=data.get("indicator_history", []),
        )

    def _derive_labels(
        self, indicators: list[MacroIndicator], data: dict[str, Any]
    ) -> dict[str, str]:
        """从 fixture 读取或简单推断四类标签。"""
        labels: dict[str, str] = {}
        for category in ("growth", "inflation", "liquidity", "market_structure"):
            key = f"{category}_label"
            if key in data:
                labels[key] = data[key]
            else:
                labels[key] = self._simple_label(category, indicators)
        return labels

    @staticmethod
    def _simple_label(category: str, indicators: list[MacroIndicator]) -> str:
        """占位规则：基于关键指标阈值给出标签。"""
        cat_inds = [ind for ind in indicators if ind.category == category]
        if not cat_inds:
            return "neutral"

        if category == "growth":
            pmi = next((ind.value for ind in cat_inds if "PMI" in ind.name), None)
            if pmi is not None:
                if pmi >= 51:
                    return "overheated"
                if pmi <= 49:
                    return "cool"
            return "neutral"

        if category == "inflation":
            cpi = next((ind.value for ind in cat_inds if "CPI" in ind.name), None)
            if cpi is not None:
                if cpi >= 2.5:
                    return "overheated"
                if cpi <= 0:
                    return "cool"
            return "neutral"

        if category == "liquidity":
            m2 = next((ind.value for ind in cat_inds if "M2" in ind.name), None)
            if m2 is not None:
                if m2 >= 10:
                    return "overheated"
                if m2 <= 7:
                    return "cool"
            return "neutral"

        if category == "market_structure":
            # 市场结构偏冷：沪深300同比跌幅较大或融资余额下降
            csi = next(
                (ind.yoy_change for ind in cat_inds if "沪深300" in ind.name), None
            )
            margin = next(
                (ind.yoy_change for ind in cat_inds if "融资" in ind.name), None
            )
            if (csi is not None and csi <= -5) or (margin is not None and margin < 0):
                return "cool"
            if csi is not None and csi >= 10:
                return "overheated"
            return "neutral"

        return "neutral"

    @staticmethod
    def _default_assessments(
        labels: dict[str, str]
    ) -> list[CapitalFlowAssessment]:
        """当 fixture 未提供四问评估时，生成占位评估。"""
        neutral: Literal["neutral"] = "neutral"
        return [
            CapitalFlowAssessment(
                question_id="Q1",
                question="M2扩张是否带来实体融资回暖？",
                answer="请补充基于事实数据的分析。",
                evidence=[],
                label=cast(
                    Literal["overheated", "neutral", "cool"],
                    labels.get("liquidity_label", neutral),
                ),
            ),
            CapitalFlowAssessment(
                question_id="Q2",
                question="政策指引方向是否明确？",
                answer="请补充基于事实数据的分析。",
                evidence=[],
                label=neutral,
            ),
            CapitalFlowAssessment(
                question_id="Q3",
                question="居民资产是否向权益迁移？",
                answer="请补充基于事实数据的分析。",
                evidence=[],
                label=cast(
                    Literal["overheated", "neutral", "cool"],
                    labels.get("market_structure_label", neutral),
                ),
            ),
            CapitalFlowAssessment(
                question_id="Q4",
                question="无风险利率趋势如何？",
                answer="请补充基于事实数据的分析。",
                evidence=[],
                label=cast(
                    Literal["overheated", "neutral", "cool"],
                    labels.get("liquidity_label", neutral),
                ),
            ),
        ]
