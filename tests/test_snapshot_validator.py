"""SnapshotValidator 结构校验测试。"""

import json
from pathlib import Path

from datetime import datetime
from decimal import Decimal

import pytest

from src.common.equity_researcher_adapter import build_research_snapshot_from_skill_output
from src.common.models import ResearchSnapshot, SourceMetadata, Valuation
from src.common.snapshot_validator import SnapshotValidator


@pytest.fixture
def full_snapshot() -> ResearchSnapshot:
    path = Path(__file__).parent / "fixtures" / "research_snapshot_full.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return build_research_snapshot_from_skill_output(
        ticker="000725.SZ",
        version="20260623120000-abc123",
        skill_output=data,
        source="test",
    )


def test_validator_passes_complete_snapshot(full_snapshot: ResearchSnapshot) -> None:
    validator = SnapshotValidator(full_snapshot)
    validator.run_all()
    assert validator.checks_passed
    assert not validator.issues


def test_validator_fails_incomplete_snapshot() -> None:
    snapshot = ResearchSnapshot(
        snapshot_id="research-000000.SH-v1",
        report_type="research",
        version="v1",
        ticker="000000.SH",
        summary="占位",
        metadata=SourceMetadata(source="test", retrieved_at=datetime.fromisoformat("2026-06-23T12:00:00"), version="1.0.0"),
    )
    validator = SnapshotValidator(snapshot)
    validator.run_all()
    assert not validator.checks_passed
    failed_names = {r.name for r in validator.results if not r.passed}
    assert "metadata" in failed_names
    assert "core_narrative" in failed_names
    assert "six_dimensions" in failed_names
    assert "investment_logic" in failed_names


def test_validator_backward_compatible_with_legacy_fields() -> None:
    snapshot = ResearchSnapshot(
        snapshot_id="research-000725.SZ-v1",
        report_type="research",
        version="v1",
        ticker="000725.SZ",
        summary="legacy report",
        six_dimensions={"H1": "c1", "H2": "c2", "H3": "c3", "H4": "c4", "H5": "c5", "H6": "c6"},
        risks=["risk"],
        assumptions=["assumption"],
        invalidation_conditions=["condition"],
        valuation=Valuation(method="PE", value_low=Decimal("4.0"), value_high=Decimal("6.0")),
        target_price_low=Decimal("4.5"),
        target_price_high=Decimal("6.0"),
        metadata=SourceMetadata(source="test", retrieved_at=datetime.fromisoformat("2026-06-23T12:00:00"), version="1.0.0"),
    )
    validator = SnapshotValidator(snapshot)
    validator.run_all()
    # 旧格式缺少新 section，校验会失败，但不应抛异常
    assert isinstance(validator.to_dict(), dict)
    assert any(r.name == "six_dimensions" and r.passed for r in validator.results)
    assert any(r.name == "core_narrative" and r.passed for r in validator.results)
    assert any(r.name == "risks" and r.passed for r in validator.results)
