"""测试分析引擎。"""

import pandas as pd

from src.analysis.technical_indicators import TechnicalIndicators


def test_technical_indicators() -> None:
    df = pd.DataFrame({
        "close": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    })
    indicators = TechnicalIndicators(df)
    rsi = indicators.rsi(5)
    assert 0 <= rsi <= 100
    ma_signal = indicators.ma_signal()
    assert isinstance(ma_signal, dict)


def test_stock_scorer() -> None:
    from src.analysis.stock_scorer import StockScorer

    scorer = StockScorer()
    financials = {
        "roe_avg_3y": 20,
        "gross_margin": 35,
        "operating_cash_flow_positive": True,
        "debt_to_asset": 0.4,
    }
    valuation = {"pe_relative": 0.6, "pb_relative": 0.7}
    prices = pd.DataFrame({"close": [10.0] * 30})

    result = scorer.score(financials, valuation, prices)
    assert "total_score" in result
    assert "conclusion" in result
