"""组合风险指标计算。"""

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


class PortfolioRisk:
    """基于持仓和价格数据计算组合风险指标。"""

    def __init__(self, positions: list[dict[str, Any]], price_data: dict[str, pd.DataFrame]) -> None:
        self.positions = positions
        self.price_data = price_data

    def returns_matrix(self) -> pd.DataFrame:
        """构建各标的日收益率矩阵。"""
        returns = {}
        for ticker, df in self.price_data.items():
            if not df.empty and "close" in df.columns:
                returns[ticker] = df["close"].pct_change().dropna()
        return pd.DataFrame(returns).dropna()

    def beta(self, ticker: str, benchmark: str) -> float:
        """计算单票相对基准的 Beta。"""
        rets = self.returns_matrix()
        if ticker not in rets.columns or benchmark not in rets.columns:
            return 0.0
        cov = rets[ticker].cov(rets[benchmark])
        var = rets[benchmark].var()
        return float(cov / var) if var else 0.0

    def value_at_risk(self, confidence: float = 0.95) -> dict[str, float]:
        """历史模拟法 VaR。"""
        rets = self.returns_matrix()
        if rets.empty:
            return {"var": 0.0, "note": "缺少收益率数据"}
        var = np.percentile(rets.mean(axis=1), (1 - confidence) * 100)
        return {"var": round(float(var), 4), "confidence": confidence}

    def concentration(self) -> dict[str, Any]:
        """持仓集中度。"""
        total_value = sum(p.get("market_value", 0) for p in self.positions)
        if not total_value:
            return {"top1": 0, "top3": 0, "top5": 0}

        sorted_positions = sorted(
            self.positions, key=lambda x: x.get("market_value", 0), reverse=True
        )
        top1 = sorted_positions[0].get("market_value", 0) / total_value if sorted_positions else 0
        top3 = sum(p.get("market_value", 0) for p in sorted_positions[:3]) / total_value
        top5 = sum(p.get("market_value", 0) for p in sorted_positions[:5]) / total_value

        return {
            "top1": round(float(top1) * 100, 2),
            "top3": round(float(top3) * 100, 2),
            "top5": round(float(top5) * 100, 2),
        }

    def sharpe_ratio(self, risk_free_rate: float = 0.025) -> float:
        """组合夏普比率（简化版）。"""
        rets = self.returns_matrix()
        if rets.empty:
            return 0.0
        portfolio_rets = rets.mean(axis=1)
        excess = portfolio_rets.mean() * 252 - risk_free_rate
        volatility = portfolio_rets.std() * np.sqrt(252)
        return float(excess / volatility) if volatility else 0.0
