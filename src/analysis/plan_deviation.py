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

    def evaluate(
        self,
        plan: TradePlan,
        latest_price: Decimal,
        latest_financials: dict[str, Any],
        latest_announcements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """返回偏离分数、等级与触发原因。"""
        score = 0.0
        triggered = []

        # 价格触发
        if plan.target_price_low and latest_price >= Decimal(str(plan.target_price_low)):
            score += self.triggers.get("price_trigger_met", 25)
            triggered.append("价格达到目标区间下限")
        if plan.target_price_high and latest_price >= Decimal(str(plan.target_price_high)):
            score += self.triggers.get("price_trigger_met", 25)
            triggered.append("价格达到目标区间上限")

        # 基本面恶化（示例：净利润同比下降）
        np_yoy = latest_financials.get("np_yoy", 0)
        if np_yoy < -20:
            score += self.triggers.get("earnings_miss", 20)
            triggered.append(f"净利润同比大幅下滑：{np_yoy}%")

        # 公告出现失效关键词（示例）
        invalid_keywords = ["终止", "撤回", "重大诉讼", "立案调查"]
        for ann in latest_announcements:
            title = ann.get("reportTitle", "")
            if any(kw in title for kw in invalid_keywords):
                score += self.triggers.get("announcement_changes_logic", 20)
                triggered.append(f"公告触发失效条件：{title}")
                break

        score = min(score, 100)

        if score >= self.levels.get("severe", {}).get("score_range", [60, 100])[0]:
            level = "severe"
            action = self.levels.get("severe", {}).get("action", "标记为假设被破坏")
        elif score >= self.levels.get("moderate", {}).get("score_range", [30, 60])[0]:
            level = "moderate"
            action = self.levels.get("moderate", {}).get("action", "要求审核")
        else:
            level = "slight"
            action = self.levels.get("slight", {}).get("action", "更新说明")

        return {
            "score": score,
            "level": level,
            "action": action,
            "triggered": triggered,
        }
