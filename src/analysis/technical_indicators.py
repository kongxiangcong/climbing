"""技术指标计算。"""

import pandas as pd


class TechnicalIndicators:
    """基于 pandas 计算常用技术指标。"""

    def __init__(self, price_df: pd.DataFrame) -> None:
        self.df = price_df.copy()
        if "close" not in self.df.columns:
            raise ValueError("价格数据必须包含 close 列")

    def sma(self, window: int) -> pd.Series:
        """简单移动平均。"""
        return self.df["close"].rolling(window=window).mean()

    def ema(self, window: int) -> pd.Series:
        """指数移动平均。"""
        return self.df["close"].ewm(span=window, adjust=False).mean()

    def rsi(self, window: int = 14) -> float:
        """相对强弱指数，返回最新值。"""
        close = self.df["close"]
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        rs = avg_gain / avg_loss
        rsi_series = 100 - (100 / (1 + rs))
        return float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """MACD 指标。"""
        ema_fast = self.ema(fast)
        ema_slow = self.ema(slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return pd.DataFrame({
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        })

    def bollinger_bands(self, window: int = 20, num_std: int = 2) -> pd.DataFrame:
        """布林带。"""
        sma = self.sma(window)
        std = self.df["close"].rolling(window=window).std()
        return pd.DataFrame({
            "middle": sma,
            "upper": sma + num_std * std,
            "lower": sma - num_std * std,
        })

    def ma_signal(self) -> dict:
        """均线多空信号。"""
        self.df["ma5"] = self.sma(5)
        self.df["ma10"] = self.sma(10)
        self.df["ma20"] = self.sma(20)

        latest = self.df.iloc[-1]
        return {
            "ma5_above_ma10": latest["ma5"] > latest["ma10"],
            "ma5_above_ma20": latest["ma5"] > latest["ma20"],
            "ma10_above_ma20": latest["ma10"] > latest["ma20"],
            "golden_cross": latest["ma5"] > latest["ma20"] and self.df["ma5"].iloc[-2] <= self.df["ma20"].iloc[-2],
        }
