"""Equity-researcher 输出到 ResearchSnapshot 的适配器测试。"""

import json
from pathlib import Path

from typing import Any

import pytest

from src.common.equity_researcher_adapter import build_research_snapshot_from_skill_output
from src.common.models import ResearchSnapshot


@pytest.fixture
def full_fixture() -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "research_snapshot_full.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_adapter_maps_all_thirteen_sections(full_fixture: dict[str, Any]) -> None:
    snapshot = build_research_snapshot_from_skill_output(
        ticker="000725.SZ",
        version="20260623120000-abc123",
        skill_output=full_fixture,
    )

    assert isinstance(snapshot, ResearchSnapshot)
    assert snapshot.ticker == "000725.SZ"
    assert snapshot.report_type == "research"
    assert snapshot.snapshot_id == "research-000725.SZ-20260623120000-abc123"

    # Section I
    assert snapshot.research_metadata is not None
    assert snapshot.research_metadata.company_name
    assert snapshot.research_metadata.market == "A-share"

    # Section II
    assert snapshot.core_narrative is not None
    assert snapshot.core_narrative.core_viewpoint

    # Section III
    assert len(snapshot.six_dimensions_typed) == 6
    assert all(d.conclusion for d in snapshot.six_dimensions_typed)

    # Section IV
    assert snapshot.investment_logic is not None
    assert snapshot.investment_logic.short_term.bull_factors
    assert snapshot.investment_logic.short_term.bear_factors

    # Section V
    assert len(snapshot.investment_thesis_table) == 4

    # Section VI
    assert snapshot.company_overview is not None
    assert snapshot.company_overview.business_segments

    # Section VII
    assert snapshot.financial_data is not None
    assert snapshot.financial_data.earnings_quality_signals

    # Section VIII
    assert snapshot.valuation.method != "unknown"
    assert snapshot.valuation_data is not None
    assert snapshot.valuation_data.comparable_companies
    assert snapshot.valuation_data.dcf is not None

    # Section IX
    assert len(snapshot.catalyst_calendar) >= 4
    high_events = [e for e in snapshot.catalyst_calendar if e.importance == "High"]
    assert len(high_events) >= 2

    # Section X
    assert "base_case" in snapshot.scenario_analysis

    # Section XI
    assert snapshot.risks
    assert snapshot.risks_typed

    # Section XII
    assert snapshot.industry_supply_chain is not None
    assert snapshot.industry_supply_chain.supply_chain

    # Section XIII
    assert snapshot.stock_price_data is not None
    assert snapshot.stock_price_data.current_price > 0


def test_adapter_backward_compatible_with_legacy_fixture() -> None:
    legacy = {
        "summary": "legacy summary",
        "six_dimensions": {"industry": "panel"},
        "valuation": {"method": "PE", "value_low": 4.0, "value_high": 6.0},
        "risks": ["risk1"],
        "assumptions": ["ass1"],
        "invalidation_conditions": ["cond1"],
        "target_price_low": 4.5,
        "target_price_high": 6.0,
    }
    snapshot = build_research_snapshot_from_skill_output(
        ticker="000725.SZ",
        version="v1",
        skill_output=legacy,
    )
    assert snapshot.summary == "legacy summary"
    assert snapshot.six_dimensions == {"industry": "panel"}
    assert snapshot.valuation.method == "PE"
    assert snapshot.risks == ["risk1"]
    assert snapshot.target_price_low == pytest.approx(4.5)
