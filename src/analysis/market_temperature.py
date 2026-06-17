"""市场温度评分器。"""

from typing import Any

import pandas as pd

from src.common.config import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


class MarketTemperature:
    """基于估值、成交、两融、市场宽度、波动、流动性评估市场温度。"""

    def __init__(self) -> None:
        self.rules = settings.get("scoring_rules.market_temperature", {})
        self.weights = self.rules.get("dimensions", {})
        self.labels = self.rules.get("labels", {})

    def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        inputs 期望字段：
        - valuation_percentile: 估值分位 0-100
        - trading_heat: 成交热度 0-100
        - margin_expansion: 两融扩张速度 0-100
        - market_breadth: 市场宽度 0-100
        - volatility_environment: 波动环境 0-100（越高越危险）
        - liquidity_environment: 流动性环境 0-100
        """
        dimensions = {}
        total_weight = sum(self.weights.values()) or 1
        weighted_score = 0.0

        for dim, weight in self.weights.items():
            value = inputs.get(dim, 50)
            # 波动率越高，对温度贡献反向
            if dim == "volatility_environment":
                contribution = value * (weight / total_weight)
            else:
                contribution = value * (weight / total_weight)
            weighted_score += contribution
            dimensions[dim] = {"value": value, "weight": weight, "contribution": contribution}

        temp = round(weighted_score, 2)

        if temp >= self.labels.get("hot", 85):
            label = "过热"
            note = "估值或成交热度偏高，注意脆弱性"
        elif temp >= self.labels.get("neutral", 65):
            label = "中性偏热"
            note = "市场状态相对健康，但赔率一般"
        elif temp >= self.labels.get("cold", 35):
            label = "中性"
            note = "市场温度适中"
        else:
            label = "偏冷"
            note = "情绪低迷，可能存在结构性机会"

        return {
            "temperature": temp,
            "label": label,
            "note": note,
            "dimensions": dimensions,
        }

    def generate_from_data(self, price_df: pd.DataFrame, macro_df: pd.DataFrame | None = None) -> dict[str, Any]:
        """从价格数据生成市场温度（占位实现，需逐步完善）。"""
        inputs = {
            "valuation_percentile": 50,
            "trading_heat": 50,
            "margin_expansion": 50,
            "market_breadth": 50,
            "volatility_environment": 50,
            "liquidity_environment": 50,
        }
        if not price_df.empty and "volume" in price_df.columns:
            # 简单示例：用 20 日成交量分位作为成交热度
            inputs["trading_heat"] = round(
                price_df["volume"].tail(20).rank(pct=True).iloc[-1] * 100, 2
            )
        return self.evaluate(inputs)
