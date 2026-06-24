"""宏观资金流事实表与快照单元测试。"""

from pathlib import Path

import pytest

from src.common.config import settings
from src.common.models import CapitalFlowSnapshot, MacroIndicator
from src.data_standardization.capital_flow import CapitalFlowStandardizer


@pytest.fixture
def standardizer() -> CapitalFlowStandardizer:
    return CapitalFlowStandardizer()


def test_standardizer_loads_fixture(standardizer: CapitalFlowStandardizer) -> None:
    data = standardizer.from_fixture()
    assert "indicators" in data
    assert "assessments" in data
    assert data["report_month"] == "2026-05"


def test_standardizer_builds_snapshot_with_four_categories(
    standardizer: CapitalFlowStandardizer,
) -> None:
    snapshot = standardizer.build_snapshot(report_month="2026-05")
    assert isinstance(snapshot, CapitalFlowSnapshot)
    assert snapshot.report_type == "capital_flow"
    assert snapshot.report_month == "2026-05"

    categories = {ind.category for ind in snapshot.indicators}
    assert categories == {"growth", "inflation", "liquidity", "market_structure"}


def test_indicator_has_source_metadata(
    standardizer: CapitalFlowStandardizer,
) -> None:
    snapshot = standardizer.build_snapshot(report_month="2026-05")
    assert snapshot.indicators
    for ind in snapshot.indicators:
        assert isinstance(ind, MacroIndicator)
        assert ind.metadata.source
        assert ind.metadata.retrieved_at is not None
        assert ind.metadata.tier is not None


def test_category_labels_are_valid(standardizer: CapitalFlowStandardizer) -> None:
    snapshot = standardizer.build_snapshot(report_month="2026-05")
    valid = {"overheated", "neutral", "cool"}
    assert snapshot.growth_label in valid
    assert snapshot.inflation_label in valid
    assert snapshot.liquidity_label in valid
    assert snapshot.market_structure_label in valid


def test_four_questions_present(
    standardizer: CapitalFlowStandardizer,
) -> None:
    snapshot = standardizer.build_snapshot(report_month="2026-05")
    assert len(snapshot.assessments) == 4
    question_ids = {a.question_id for a in snapshot.assessments}
    assert question_ids == {"Q1", "Q2", "Q3", "Q4"}
    for assessment in snapshot.assessments:
        assert assessment.question
        assert assessment.answer
        assert assessment.label in {"overheated", "neutral", "cool"}


def test_fixture_file_exists() -> None:
    fixture = settings.project_root / "tests" / "fixtures" / "capital_flow.json"
    assert fixture.exists()
    assert fixture.stat().st_size > 0
