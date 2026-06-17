"""证券主数据标准化。"""

from pathlib import Path

import pandas as pd

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import Security, SourceMetadata
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class SecurityMaster:
    """证券主数据表管理。"""

    TABLE_NAME = "security_master.parquet"

    def __init__(self) -> None:
        self.output_dir = get_data_dir("standardized")
        self.output_path = self.output_dir / self.TABLE_NAME

    def load(self) -> pd.DataFrame:
        """加载证券主数据表。"""
        if self.output_path.exists():
            return pd.read_parquet(self.output_path)
        return pd.DataFrame(columns=["ticker", "name", "market", "sector", "industry", "tags"])

    def save(self, securities: list[Security]) -> Path:
        """保存证券主数据表。"""
        records = []
        for s in securities:
            record = s.model_dump()
            if s.metadata:
                record["source"] = s.metadata.source
                record["retrieved_at"] = s.metadata.retrieved_at
                record["version"] = s.metadata.version
            records.append(record)

        df = pd.DataFrame(records)
        df.to_parquet(self.output_path, index=False)
        logger.info("Saved security master: %s rows -> %s", len(df), self.output_path)
        return self.output_path

    def add_from_watchlist(self) -> Path:
        """从 config/tickers.yaml 加载关注列表到证券主数据表。"""
        import yaml

        watchlist_path = Path(settings.project_root) / "config" / "tickers.yaml"
        with watchlist_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        securities = []
        for item in data.get("watchlist", []):
            securities.append(
                Security(
                    ticker=item["ticker"],
                    name=item["name"],
                    market=item["ticker"].split(".")[-1],
                    sector=item.get("sector"),
                    industry=item.get("industry"),
                    tags=item.get("tags", []),
                )
            )

        return self.save(securities)
