"""价格与指标表标准化。"""

from pathlib import Path

import pandas as pd

from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class PriceMetricsStandardizer:
    """价格数据标准化。"""

    TABLE_NAME = "price_metrics.parquet"

    def __init__(self) -> None:
        self.output_dir = get_data_dir("standardized")
        self.output_path = self.output_dir / self.TABLE_NAME

    def load(self) -> pd.DataFrame:
        if self.output_path.exists():
            return pd.read_parquet(self.output_path)
        return pd.DataFrame()

    def standardize(
        self,
        ticker: str,
        source_file: Path,
        source_name: str = "stock_finance_data",
    ) -> pd.DataFrame:
        """读取原始价格数据并标准化。"""
        df = pd.read_csv(source_file)
        df["ticker"] = ticker
        df["source"] = source_name
        df["retrieved_at"] = pd.Timestamp.now()
        df["version"] = "1.0.0"
        # 统一日期列
        if "time" in df.columns:
            df["trade_date"] = pd.to_datetime(df["time"]).dt.date
        elif "Date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["Date"]).dt.date
        return df

    def append(self, df: pd.DataFrame) -> Path:
        """追加到价格表。"""
        existing = self.load()
        combined = pd.concat([existing, df], ignore_index=True)
        if "ticker" in combined.columns and "trade_date" in combined.columns:
            combined = combined.drop_duplicates(subset=["ticker", "trade_date"], keep="last")
        combined.to_parquet(self.output_path, index=False)
        logger.info("Saved price metrics: %s rows -> %s", len(combined), self.output_path)
        return self.output_path
