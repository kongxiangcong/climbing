"""财务事实表标准化。"""

from pathlib import Path

import pandas as pd

from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class FinancialFactsStandardizer:
    """财务数据标准化。"""

    TABLE_NAME = "financial_facts.parquet"

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
        report_date: str,
        source_file: Path,
        source_name: str = "stock_finance_data",
    ) -> pd.DataFrame:
        """读取原始财务报表并标准化。"""
        df = pd.read_csv(source_file)
        df["ticker"] = ticker
        df["report_date"] = report_date
        df["source"] = source_name
        df["retrieved_at"] = pd.Timestamp.now()
        df["version"] = "1.0.0"
        return df

    def append(self, df: pd.DataFrame) -> Path:
        """追加到财务事实表。"""
        existing = self.load()
        combined = pd.concat([existing, df], ignore_index=True)
        # 去重：ticker + report_date + source 维度保留最新
        combined = combined.drop_duplicates(
            subset=[c for c in ["ticker", "report_date", "source"] if c in combined.columns],
            keep="last",
        )
        combined.to_parquet(self.output_path, index=False)
        logger.info("Saved financial facts: %s rows -> %s", len(combined), self.output_path)
        return self.output_path
