"""stock_finance_data 数据源客户端封装。"""

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


class StockFinanceDataClient:
    """stock_finance_data API 客户端。"""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or get_data_dir("raw") / "stock_finance_data"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = settings.get("data_sources.stock_finance_data.enabled", True)

    def _save_path(self, name: str) -> Path:
        return self.raw_dir / name

    def fetch_stock_info(self, ticker: str) -> Path:
        """获取公司基本信息。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_stock_info.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_stock_info",
            params={"ticker": ticker, "file_path": str(path)},
        )
        logger.info("Fetched stock info for %s -> %s", ticker, path)
        return path

    def fetch_financial_statements(
        self, ticker: str, report_date: str, statement: str = "all"
    ) -> Path:
        """获取财务报表。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_fs_{report_date}.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_financial_statements",
            params={
                "ticker": ticker,
                "statement": statement,
                "financial_parameter": report_date,
                "file_path": str(path),
            },
        )
        logger.info("Fetched financial statements for %s %s -> %s", ticker, report_date, path)
        return path

    def fetch_price(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "D",
        adjust: str = "forward",
    ) -> Path:
        """获取历史行情。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_price_{start_date}_{end_date}_{interval}.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_price",
            params={
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "interval": interval,
                "adjust": adjust,
                "file_path": str(path),
            },
        )
        logger.info("Fetched price for %s -> %s", ticker, path)
        return path

    def fetch_holder_info(self, ticker: str) -> Path:
        """获取股东信息。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_holder.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_holder_info",
            params={"ticker": ticker, "file_path": str(path)},
        )
        logger.info("Fetched holder info for %s -> %s", ticker, path)
        return path

    def fetch_announcements(self, ticker: str, start_date: str, end_date: str) -> Path:
        """获取公司公告。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_announcements_{start_date}_{end_date}.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_stock_announcement",
            params={
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "file_path": str(path),
            },
        )
        logger.info("Fetched announcements for %s -> %s", ticker, path)
        return path

    def fetch_forecast(self, ticker: str) -> Path:
        """获取盈利预测。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_forecast.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_forecast",
            params={"ticker": ticker, "file_path": str(path)},
        )
        logger.info("Fetched forecast for %s -> %s", ticker, path)
        return path

    def fetch_financial_index(
        self, ticker: str, report_date: str, category: str
    ) -> Path:
        """获取财务指标。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(f"{ticker}_finidx_{category}_{report_date}.csv")
        call_data_source_tool(
            data_source_name="stock_finance_data",
            api_name="stock_finance_data_get_stock_financial_index",
            params={
                "ticker": ticker,
                "financial_parameter": report_date,
                "category": category,
                "file_path": str(path),
            },
        )
        logger.info("Fetched financial index for %s %s -> %s", ticker, category, path)
        return path
