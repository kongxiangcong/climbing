"""计划偏离评分器单元测试。"""

from decimal import Decimal

import pytest

from src.analysis.plan_deviation import PlanDeviationScorer
from src.common.models import TradeBatch, TradePlan, TradePlanStatus


def _sample_plan(
    target_low: Decimal = Decimal("4.8"),
    target_high: Decimal = Decimal("6.2"),
    stop_loss: Decimal | None = Decimal("4.46"),
    take_profit: Decimal | None = Decimal("6.2"),
) -> TradePlan:
    return TradePlan(
        plan_id="000725.SZ-test",
        name="测试计划",
        ticker="000725.SZ",
        direction="long",
        time_window="3-6m",
        research_version="v1",
        entry_logic="test entry",
        exit_logic="test exit",
        target_price_low=target_low,
        target_price_high=target_high,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_limit=Decimal("10"),
        risk_budget=Decimal("2"),
        status=TradePlanStatus.ACTIVE,
        plan_version="1",
    )


def test_price_trigger_in_target_range() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    result = scorer.evaluate(plan, Decimal("5.2"), {}, [])

    assert result["score"] > 0
    assert any("价格触发" in t for t in result["triggered"])
    assert result["level"] in ("slight", "moderate", "severe")


def test_price_trigger_at_upper_bound_is_severe() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    result = scorer.evaluate(plan, Decimal("6.5"), {}, [])

    assert result["score"] >= 60
    assert any("目标区间上限" in t for t in result["triggered"])
    assert result["level"] == "severe"


def test_stop_loss_trigger() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    result = scorer.evaluate(plan, Decimal("4.3"), {}, [])

    assert any("跌破止损价" in t for t in result["triggered"])
    assert result["score"] >= 30


def test_earnings_miss_trigger() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    result = scorer.evaluate(plan, Decimal("4.5"), {"np_yoy": -35}, [])

    assert any("净利润同比大幅下滑" in t for t in result["triggered"])
    assert result["score"] >= 20


@pytest.mark.parametrize(
    "keyword",
    ["终止", "重大诉讼", "立案调查"],
)
def test_announcement_keyword_triggers_deviation(keyword: str) -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    announcements = [{"reportTitle": f"公司收到{keyword}通知的公告"}]
    result = scorer.evaluate(plan, Decimal("4.5"), {}, announcements)

    assert any("事件触发" in t for t in result["triggered"])
    assert result["score"] >= 20


def test_no_trigger_returns_slight() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    result = scorer.evaluate(plan, Decimal("4.5"), {"np_yoy": 5}, [])

    assert result["score"] == 0
    assert result["level"] == "slight"
    assert not result["triggered"]


def test_multiple_triggers_aggregate_score() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    announcements = [{"reportTitle": "关于收到立案调查通知书的公告"}]
    financials = {"np_yoy": -35}
    result = scorer.evaluate(plan, Decimal("6.5"), financials, announcements)

    assert result["score"] >= 60
    assert result["level"] == "severe"
    assert len(result["triggered"]) >= 3


def test_score_is_capped_at_100() -> None:
    plan = _sample_plan()
    scorer = PlanDeviationScorer()
    announcements = [{"reportTitle": "关于收到立案调查通知书的公告"}]
    financials = {"np_yoy": -35}
    result = scorer.evaluate(plan, Decimal("6.5"), financials, announcements)

    assert result["score"] <= 100
