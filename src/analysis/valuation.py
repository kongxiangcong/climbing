"""估值分析。"""

from decimal import Decimal
from typing import Any

import pandas as pd


class ValuationAnalyzer:
    """个股估值分析。"""

    def __init__(self, financials: dict[str, Any], prices: pd.DataFrame | None = None) -> None:
        self.financials = financials
        self.prices = prices

    def pe(self) -> dict[str, Any]:
        """市盈率分析。"""
        eps = self.financials.get("eps", 0)
        if not eps or self.prices is None or self.prices.empty:
            return {"pe_ttm": None, "note": "缺少 EPS 或价格数据"}
        latest_price = float(self.prices["close"].iloc[-1])
        pe = latest_price / eps if eps else None
        return {"pe_ttm": round(pe, 2) if pe else None, "latest_price": latest_price, "eps": eps}

    def pb(self) -> dict[str, Any]:
        """市净率分析。"""
        bps = self.financials.get("bps", 0)
        if not bps or self.prices is None or self.prices.empty:
            return {"pb": None, "note": "缺少 BPS 或价格数据"}
        latest_price = float(self.prices["close"].iloc[-1])
        pb = latest_price / bps if bps else None
        return {"pb": round(pb, 2) if pb else None, "latest_price": latest_price, "bps": bps}

    def summary(self) -> dict[str, Any]:
        """估值摘要。"""
        return {
            "pe": self.pe(),
            "pb": self.pb(),
            "note": "相对估值需结合行业基准，当前为绝对估值占位",
        }
