"""宏观时间序列标准化。"""

from pathlib import Path

import pandas as pd

from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class MacroSeriesStandardizer:
    """宏观数据标准化。"""

    TABLE_NAME = "macro_series.parquet"

    def __init__(self) -> None:
        self.output_dir = get_data_dir("standardized")
        self.output_path = self.output_dir / self.TABLE_NAME

    def load(self) -> pd.DataFrame:
        if self.output_path.exists():
            return pd.read_parquet(self.output_path)
        return pd.DataFrame()

    def standardize(self, source_file: Path, source_name: str = "world_bank") -> pd.DataFrame:
        df = pd.read_csv(source_file)
        df["source"] = source_name
        df["retrieved_at"] = pd.Timestamp.now()
        df["version"] = "1.0.0"
        return df

    def append(self, df: pd.DataFrame) -> Path:
        existing = self.load()
        combined = pd.concat([existing, df], ignore_index=True)
        if {"indicator", "country", "date"}.issubset(combined.columns):
            combined = combined.drop_duplicates(
                subset=["indicator", "country", "date"], keep="last"
            )
        combined.to_parquet(self.output_path, index=False)
        logger.info("Saved macro series: %s rows -> %s", len(combined), self.output_path)
        return self.output_path
