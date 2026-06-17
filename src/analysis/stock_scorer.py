"""个股研究评分器。"""

from decimal import Decimal
from typing import Any

import pandas as pd

from src.common.config import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


class StockScorer:
    """基于财务、估值、技术面对个股进行综合评分。"""

    def __init__(self) -> None:
        self.rules = settings.get("scoring_rules.stock_scorer", {})
        self.weights = self.rules.get("weights", {})
        self.thresholds = self.rules.get("thresholds", {})

    def score_fundamental_quality(self, financials: dict[str, Any]) -> dict[str, Any]:
        """基本面质量评分。"""
        score = 0.0
        details = {}

        roe = financials.get("roe_avg_3y", 0)
        if roe >= 15:
            score += 8
            details["roe"] = "优秀"
        elif roe >= 10:
            score += 5
            details["roe"] = "良好"
        else:
            details["roe"] = "偏弱"

        gm = financials.get("gross_margin", 0)
        if gm >= 30:
            score += 7
            details["gross_margin"] = "优秀"
        elif gm >= 20:
            score += 4
            details["gross_margin"] = "良好"
        else:
            details["gross_margin"] = "偏弱"

        if financials.get("operating_cash_flow_positive", False):
            score += 8
            details["ocf"] = "为正"
        else:
            details["ocf"] = "为负"

        if financials.get("debt_to_asset", 1) < 0.6:
            score += 7
            details["leverage"] = "合理"
        else:
            details["leverage"] = "偏高"

        return {"score": score, "max": 30, "details": details}

    def score_valuation(self, valuation: dict[str, Any]) -> dict[str, Any]:
        """估值吸引力评分。"""
        score = 0.0
        details = {}

        pe_relative = valuation.get("pe_relative", 1.0)
        if pe_relative < 0.5:
            score += 10
            details["pe_relative"] = "显著低估"
        elif pe_relative < 1.0:
            score += 6
            details["pe_relative"] = "合理偏低"
        else:
            details["pe_relative"] = "偏高"

        pb_relative = valuation.get("pb_relative", 1.0)
        if pb_relative < 0.5:
            score += 10
            details["pb_relative"] = "显著低估"
        elif pb_relative < 1.0:
            score += 6
            details["pb_relative"] = "合理偏低"
        else:
            details["pb_relative"] = "偏高"

        return {"score": score, "max": 20, "details": details}

    def score_technical(self, prices: pd.DataFrame) -> dict[str, Any]:
        """技术面评分（基于均线、趋势）。"""
        from src.analysis.technical_indicators import TechnicalIndicators

        score = 0.0
        details = {}

        if prices.empty or "close" not in prices.columns:
            return {"score": 0, "max": 15, "details": {"error": "缺少价格数据"}}

        indicators = TechnicalIndicators(prices)
        ma_signals = indicators.ma_signal()

        if ma_signals.get("ma5_above_ma20", False):
            score += 8
            details["ma_trend"] = "多头排列"
        else:
            details["ma_trend"] = "空头或震荡"

        rsi = indicators.rsi(14)
        if 40 <= rsi <= 60:
            score += 4
            details["rsi"] = "中性健康"
        elif rsi > 60:
            details["rsi"] = "偏强"
        else:
            details["rsi"] = "偏弱"

        return {"score": score, "max": 15, "details": details}

    def score(
        self,
        financials: dict[str, Any],
        valuation: dict[str, Any],
        prices: pd.DataFrame,
    ) -> dict[str, Any]:
        """返回总分与各维度评分。"""
        fundamental = self.score_fundamental_quality(financials)
        val = self.score_valuation(valuation)
        tech = self.score_technical(prices)

        # 趋势与预期差占位
        trend = {"score": 10, "max": 20, "details": {"note": "需接入一致预期与边际变化"}}
        # 风险暴露占位
        risk = {"score": 10, "max": 15, "details": {"note": "需接入波动率、集中度、行业风险"}}

        total = (
            fundamental["score"]
            + trend["score"]
            + val["score"]
            + tech["score"]
            + risk["score"]
        )
        max_total = (
            fundamental["max"]
            + trend["max"]
            + val["max"]
            + tech["max"]
            + risk["max"]
        )

        if total >= self.thresholds.get("plan", 75):
            conclusion = "可计划"
        elif total >= self.thresholds.get("watch", 60):
            conclusion = "可跟踪"
        else:
            conclusion = "不可碰"

        return {
            "total_score": total,
            "max_score": max_total,
            "score_pct": round(total / max_total * 100, 2) if max_total else 0,
            "conclusion": conclusion,
            "dimensions": {
                "fundamental_quality": fundamental,
                "trend_and_expectation": trend,
                "valuation": val,
                "technical_behavior": tech,
                "risk_exposure": risk,
            },
        }
