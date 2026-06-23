"""交易计划 schema、状态机与持久化测试。"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.analysis.plan_state_machine import (
    PlanStateMachine,
    PlanStateMachineError,
    is_terminal_status,
    status_display_name,
)
from src.common.models import (
    PlanAuditLogEntry,
    TradeBatch,
    TradePlan,
    TradePlanStatus,
)
from src.common.plan_io import (
    build_plan_id,
    link_transaction_to_plan,
    list_plan_ids,
    load_plan,
    plan_path,
    save_plan,
    write_plans_web_summary,
)


def _sample_plan(**overrides: object) -> TradePlan:
    defaults = {
        "plan_id": "000725.SZ-test",
        "name": "测试计划",
        "ticker": "000725.SZ",
        "direction": "long",
        "time_window": "3-6m",
        "research_version": "v1",
        "entry_logic": "test entry",
        "exit_logic": "test exit",
        "target_price_low": Decimal("4.8"),
        "target_price_high": Decimal("6.2"),
        "stop_loss": Decimal("4.46"),
        "take_profit": Decimal("6.2"),
        "position_limit": Decimal("10"),
        "initial_position_pct": Decimal("3"),
        "max_position_pct": Decimal("10"),
        "risk_budget": Decimal("2"),
        "expected_return": Decimal("15"),
        "invalidation_conditions": ["条件1"],
        "alternative_scenarios": ["情景1"],
        "triggers": ["触发1"],
        "batch_strategy": [
            TradeBatch(
                batch_id="1",
                target_price_low=Decimal("4.8"),
                target_price_high=Decimal("5.5"),
                allocation_pct=Decimal("40"),
            ),
            TradeBatch(
                batch_id="2",
                target_price_low=Decimal("5.5"),
                target_price_high=Decimal("6.2"),
                allocation_pct=Decimal("60"),
            ),
        ],
        "review_frequency": "weekly",
    }
    defaults.update(overrides)
    return TradePlan(**defaults)  # type: ignore[arg-type]


def test_trade_plan_schema_required_fields() -> None:
    plan = _sample_plan()
    assert plan.ticker == "000725.SZ"
    assert plan.direction == "long"
    assert plan.position_limit == Decimal("10")
    assert len(plan.batch_strategy) == 2
    assert plan.batch_strategy[0].allocation_pct == Decimal("40")


def test_trade_plan_batch_allocation_pct_validation() -> None:
    with pytest.raises(ValueError):
        TradeBatch(allocation_pct=Decimal("120"))


def test_state_machine_draft_to_active_requires_confirmation() -> None:
    plan = _sample_plan(status=TradePlanStatus.DRAFT, plan_version="1")
    machine = PlanStateMachine(plan)

    with pytest.raises(PlanStateMachineError, match="用户确认"):
        machine.activate(user_confirmed=False)

    machine.activate(user_confirmed=True, reason="test")
    assert plan.status == TradePlanStatus.ACTIVE
    assert plan.plan_version == "2"


def test_state_machine_all_valid_transitions() -> None:
    transitions = [
        (TradePlanStatus.DRAFT, TradePlanStatus.ACTIVE),
        (TradePlanStatus.ACTIVE, TradePlanStatus.PARTIALLY_TRIGGERED),
        (TradePlanStatus.ACTIVE, TradePlanStatus.FULLY_TRIGGERED),
        (TradePlanStatus.ACTIVE, TradePlanStatus.ASSUMPTION_BROKEN),
        (TradePlanStatus.PARTIALLY_TRIGGERED, TradePlanStatus.FULLY_TRIGGERED),
        (TradePlanStatus.PARTIALLY_TRIGGERED, TradePlanStatus.ASSUMPTION_BROKEN),
        (TradePlanStatus.FULLY_TRIGGERED, TradePlanStatus.CLOSED),
        (TradePlanStatus.ASSUMPTION_BROKEN, TradePlanStatus.CLOSED),
        (TradePlanStatus.CLOSED, TradePlanStatus.REVIEWED),
    ]
    for start, end in transitions:
        plan = _sample_plan(status=start, plan_version="1")
        machine = PlanStateMachine(plan)
        assert machine.can_transition(end)
        machine.transition(end, user_confirmed=True, reason="test")
        assert plan.status == end


def test_state_machine_rejects_invalid_transition() -> None:
    plan = _sample_plan(status=TradePlanStatus.DRAFT, plan_version="1")
    machine = PlanStateMachine(plan)
    assert not machine.can_transition(TradePlanStatus.CLOSED)
    with pytest.raises(PlanStateMachineError):
        machine.transition(TradePlanStatus.CLOSED, user_confirmed=True)


def test_state_machine_version_bump() -> None:
    plan = _sample_plan(status=TradePlanStatus.DRAFT, plan_version="3")
    machine = PlanStateMachine(plan)
    machine.activate(user_confirmed=True)
    assert plan.plan_version == "4"


def test_state_machine_audit_log_entries() -> None:
    plan = _sample_plan(status=TradePlanStatus.DRAFT, plan_version="1")
    machine = PlanStateMachine(plan)
    machine.activate(user_confirmed=True, reason="用户确认")
    assert len(plan.audit_log) == 1
    entry = plan.audit_log[0]
    assert entry.from_status == TradePlanStatus.DRAFT
    assert entry.to_status == TradePlanStatus.ACTIVE
    assert entry.user_confirmed is True
    assert entry.previous_version == "1"
    assert entry.new_version == "2"


def test_state_machine_terminal_status() -> None:
    plan = _sample_plan(status=TradePlanStatus.REVIEWED, plan_version="5")
    machine = PlanStateMachine(plan)
    assert is_terminal_status(plan.status)
    assert machine.allowed_transitions() == []


def test_status_display_name_mapping() -> None:
    assert status_display_name(TradePlanStatus.DRAFT) == "草稿"
    assert status_display_name(TradePlanStatus.ACTIVE) == "激活"


def test_plan_persistence_roundtrip(tmp_path: Path) -> None:
    # 临时重定向 data/user/plans 目录
    from src.common import plan_io as plan_io_module

    original_dir = plan_io_module.plans_dir
    custom_dir = tmp_path / "plans"
    custom_dir.mkdir(parents=True, exist_ok=True)

    def _custom_plans_dir() -> Path:
        custom_dir.mkdir(parents=True, exist_ok=True)
        return custom_dir

    plan_io_module.plans_dir = _custom_plans_dir
    try:
        plan = _sample_plan(plan_id="roundtrip-1")
        path = save_plan(plan)
        assert path.exists()

        loaded = load_plan(plan.plan_id)
        assert loaded.plan_id == plan.plan_id
        assert loaded.status == plan.status
        assert loaded.batch_strategy[0].allocation_pct == Decimal("40")
    finally:
        plan_io_module.plans_dir = original_dir


def test_plan_io_build_id() -> None:
    plan_id = build_plan_id("000725.SZ", "测试")
    assert plan_id.startswith("000725.SZ-")
    assert len(plan_id) > len("000725.SZ-")


def test_link_transaction_to_plan() -> None:
    plan = _sample_plan()
    link_transaction_to_plan(
        plan=plan,
        transaction_id="tx-1",
        ticker="000725.SZ",
        side="buy",
        quantity=100,
        price="4.85",
        fee="5",
    )
    assert "tx-1" in plan.linked_transaction_ids
    assert len(plan.execution_records) == 1
    assert plan.execution_records[0].price == Decimal("4.85")


def test_write_plans_web_summary(tmp_path: Path) -> None:
    from src.common import config as config_module
    from src.common import plan_io as plan_io_module

    original_plans_dir = plan_io_module.plans_dir
    custom_plans = tmp_path / "plans"
    custom_plans.mkdir(parents=True, exist_ok=True)

    original_root = config_module.settings.project_root
    config_module.settings.project_root = tmp_path

    def _custom_plans_dir() -> Path:
        custom_plans.mkdir(parents=True, exist_ok=True)
        return custom_plans

    plan_io_module.plans_dir = _custom_plans_dir
    try:
        plan = _sample_plan(plan_id="web-1")
        save_plan(plan)
        web_path = write_plans_web_summary()
        assert web_path.exists()
        data = json.loads(web_path.read_text(encoding="utf-8"))
        assert data["count"] == 1
        assert data["plans"][0]["plan_id"] == "web-1"
        assert data["plans"][0]["status_display"] == "草稿"
    finally:
        plan_io_module.plans_dir = original_plans_dir
        config_module.settings.project_root = original_root
