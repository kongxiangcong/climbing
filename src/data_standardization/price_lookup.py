"""最新价格查询（本地优先）。

优先从 ``data/{code}_price.csv``、``data/raw/{code}_realtime_price.csv`` 等本地文件中
读取收盘价；未命中时返回 ``None``，由调用方决定如何回退。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.config import settings

TICKER_COLUMNS = {"ts_code", "ticker", "code", "symbol", "股票代码"}
PRICE_COLUMNS = {"close", "price", "收盘价", "最新价", "收盘"}
TIME_COLUMNS = {"time", "trade_date", "date", "datetime", "交易时间", "日期"}


def _detect_columns(df: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    """从 DataFrame 中识别 ticker / close / time 列。"""
    cols = {c.strip().lower() for c in df.columns}
    ticker_col = next(
        (c for c in df.columns if c.strip().lower() in TICKER_COLUMNS), None
    )
    price_col = next(
        (c for c in df.columns if c.strip().lower() in PRICE_COLUMNS), None
    )
    time_col = next(
        (c for c in df.columns if c.strip().lower() in TIME_COLUMNS), None
    )
    return ticker_col, price_col, time_col


def _parse_time(value: Any) -> datetime:
    """尝试多种时间格式。"""
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间：{value}")


def _load_price_from_csv(path: Path, ticker: str, code: str) -> Decimal | None:
    """从单个 CSV 中查找指定代码的最新收盘价。"""
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return None

    if df.empty:
        return None

    ticker_col, price_col, time_col = _detect_columns(df)
    if price_col is None:
        return None

    if ticker_col is not None:
        # 统一比较时去掉空格并转为字符串
        mask = df[ticker_col].astype(str).str.strip().isin({ticker, code})
        df = df[mask]
        if df.empty:
            return None

    if time_col is not None:
        try:
            df["_parsed_time"] = df[time_col].apply(_parse_time)
            df = df.sort_values("_parsed_time", ascending=False)
        except Exception:
            # 时间无法解析时保留原顺序，取最后一行
            df = df.iloc[-1:]
    else:
        df = df.iloc[-1:]

    value = str(df.iloc[0][price_col]).replace(",", "").strip()
    try:
        return Decimal(value)
    except Exception:
        return None


def load_latest_price(ticker: str) -> Decimal | None:
    """获取 ``ticker`` 的最新收盘价（Decimal）。

    搜索路径：
      - ``data/{code}_price.csv``
      - ``data/raw/{code}_price.csv``
      - ``data/raw/{code}_realtime_price.csv``
      - ``data/raw/verification/verify_price.csv``
    """
    code = ticker.split(".")[0]
    candidates = [
        settings.project_root / "data" / f"{code}_price.csv",
        settings.project_root / "data" / "raw" / f"{code}_price.csv",
        settings.project_root / "data" / "raw" / f"{code}_realtime_price.csv",
        settings.project_root / "data" / "raw" / "verification" / "verify_price.csv",
    ]

    for path in candidates:
        price = _load_price_from_csv(path, ticker, code)
        if price is not None:
            return price
    return None
