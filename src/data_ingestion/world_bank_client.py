"""World Bank Open Data 客户端封装。"""

from pathlib import Path

from src.common.config import settings
from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class WorldBankClient:
    """World Bank Open Data API 客户端。"""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or get_data_dir("raw") / "world_bank"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = settings.get("data_sources.world_bank.enabled", True)

    def _save_path(self, name: str) -> Path:
        return self.raw_dir / name

    def search_indicators(self, query: str) -> dict:
        """搜索指标代码。"""
        from mcp__plugin-kimi-datasource_data import call_data_source_tool

        result = call_data_source_tool(
            data_source_name="world_bank_open_data",
            api_name="world_bank_search_indicators",
            params={"query": query},
        )
        logger.info("Searched World Bank indicators for '%s'", query)
        return result

    def fetch_data(
        self,
        country: str,
        indicators: str,
        date_range: str | None = None,
        most_recent: int | None = None,
    ) -> Path:
        """获取宏观数据。"""
        from mcp__plugin-kimi-datasource_data import call_data_source_tool

        name = f"{country}_{indicators.replace(',', '_')}"
        if date_range:
            name += f"_{date_range}"
        if most_recent:
            name += f"_last{most_recent}"
        path = self._save_path(f"{name}.csv")

        params: dict = {"country": country, "indicator": indicators, "filepath": str(path)}
        if date_range:
            params["date_range"] = date_range
        if most_recent:
            params["most_recent"] = most_recent

        call_data_source_tool(
            data_source_name="world_bank_open_data",
            api_name="world_bank_open_data",
            params=params,
        )
        logger.info("Fetched World Bank data %s -> %s", name, path)
        return path
