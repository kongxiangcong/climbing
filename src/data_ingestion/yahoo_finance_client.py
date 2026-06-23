"""Yahoo Finance 数据源客户端封装。"""

from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


def _get_data_source_tool() -> Any:
    """Kimi datasource 工具在运行时被注入，不能作为普通 Python 模块 import。"""
    tool = __import__("mcp__plugin-kimi-datasource_data")
    return getattr(tool, "call_data_source_tool")


class YahooFinanceClient:
    """Yahoo Finance API 客户端。"""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or get_data_dir("raw") / "yahoo_finance"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = settings.get("data_sources.yahoo_finance.enabled", True)

    def _save_path(self, name: str) -> Path:
        return self.raw_dir / name

    def fetch_stock_info(self, ticker: str) -> Path:
        """获取公司信息。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_stock_info.csv")
        call_data_source_tool(
            data_source_name="yahoo_finance",
            api_name="get_stock_info",
            params={"ticker": ticker, "file_path": str(path)},
        )
        logger.info("Fetched Yahoo stock info for %s -> %s", ticker, path)
        return path

    def fetch_historical_prices(
        self, ticker: str, period: str = "1mo", interval: str = "1d"
    ) -> Path:
        """获取历史行情。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_price_{period}_{interval}.csv")
        call_data_source_tool(
            data_source_name="yahoo_finance",
            api_name="get_historical_stock_prices",
            params={"ticker": ticker, "period": period, "interval": interval, "file_path": str(path)},
        )
        logger.info("Fetched Yahoo historical prices for %s -> %s", ticker, path)
        return path

    def fetch_financial_statement(self, ticker: str, financial_type: str) -> Path:
        """获取财务报表。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_{financial_type}.csv")
        call_data_source_tool(
            data_source_name="yahoo_finance",
            api_name="get_financial_statement",
            params={"ticker": ticker, "financial_type": financial_type, "file_path": str(path)},
        )
        logger.info("Fetched Yahoo financial statement for %s -> %s", ticker, path)
        return path

    def fetch_recommendations(self, ticker: str) -> Path:
        """获取分析师推荐。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_recommendations.csv")
        call_data_source_tool(
            data_source_name="yahoo_finance",
            api_name="get_recommendations",
            params={"ticker": ticker, "recommendation_type": "all", "file_path": str(path)},
        )
        logger.info("Fetched Yahoo recommendations for %s -> %s", ticker, path)
        return path
