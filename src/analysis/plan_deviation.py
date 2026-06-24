"""计划偏离评分器。"""

from decimal import Decimal
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import TradePlan

logger = get_logger(__name__)


class PlanDeviationScorer:
    """评估当前行情相对交易计划的偏离程度。"""

    def __init__(self) -> None:
        self.rules = settings.get("scoring_rules.plan_deviation", {})
        self.triggers = self.rules.get("triggers", {})
        self.levels = self.rules.get("levels", {})

    def _trigger_weight(self, key: str, default: float) -> float:
        return float(self.triggers.get(key, default))

    def _level_threshold(self, key: str) -> float:
        defaults = {"slight": 0, "moderate": 30, "severe": 60}
        range_start = self.levels.get(key, {}).get("score_range", [defaults[key], 100])[0]
        return float(range_start)

    def _level_action(self, key: str, default: str) -> str:
        return str(self.levels.get(key, {}).get("action", default))

    def evaluate(
        self,
        plan: TradePlan,
        latest_price: Decimal,
        latest_financials: dict[str, Any],
        latest_announcements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """返回偏离分数、等级与触发原因。"""
        score = 0.0
        triggered: list[str] = []

        # 价格触发：进入目标区间
        if plan.target_price_low and latest_price >= Decimal(str(plan.target_price_low)):
            score += self._trigger_weight("price_trigger_met", 25)
            triggered.append("价格触发：达到目标区间下限")
        if plan.target_price_high and latest_price >= Decimal(str(plan.target_price_high)):
            score += self._trigger_weight("price_trigger_met", 25)
            triggered.append("价格触发：达到目标区间上限")

        # 止损 / 止盈触发
        if plan.stop_loss and latest_price <= Decimal(str(plan.stop_loss)):
            score += self._trigger_weight("stop_loss_triggered", 30)
            triggered.append("价格触发：跌破止损价")
        if plan.take_profit and latest_price >= Decimal(str(plan.take_profit)):
            score += self._trigger_weight("take_profit_triggered", 25)
            triggered.append("价格触发：达到止盈价")

        # 基本面恶化：净利润同比下降
        np_yoy = latest_financials.get("np_yoy", 0)
        if np_yoy < -20:
            score += self._trigger_weight("earnings_miss", 20)
            triggered.append(f"基本面触发：净利润同比大幅下滑 {np_yoy}%")

        # 公告出现失效关键词
        invalid_keywords = ["终止", "撤回", "重大诉讼", "立案调查"]
        for ann in latest_announcements:
            title = ann.get("reportTitle", "")
            if any(kw in title for kw in invalid_keywords):
                score += self._trigger_weight("announcement_changes_logic", 20)
                triggered.append(f"事件触发：公告触发失效条件 {title}")
                break

        score = min(score, 100)

        if score >= self._level_threshold("severe"):
            level = "severe"
            action = self._level_action("severe", "标记为假设被破坏")
        elif score >= self._level_threshold("moderate"):
            level = "moderate"
            action = self._level_action("moderate", "要求审核")
        else:
            level = "slight"
            action = self._level_action("slight", "更新说明")

        return {
            "score": score,
            "level": level,
            "action": action,
            "triggered": triggered,
        }
