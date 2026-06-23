"""天眼查企业数据客户端封装。"""

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


class TianyanchaClient:
    """天眼查 API 客户端。"""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or get_data_dir("raw") / "tianyancha"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = settings.get("data_sources.tianyancha.enabled", True)

    def _save_path(self, name: str) -> Path:
        return self.raw_dir / name

    def search_apis(self, query: str, limit: int = 10) -> dict[str, Any]:
        """搜索可用 API。"""
        call_data_source_tool = _get_data_source_tool()

        result: dict[str, Any] = call_data_source_tool(
            data_source_name="tianyancha",
            api_name="tianyancha_api_search",
            params={"query": query, "limit": str(limit)},
        )
        return result

    def call_api(self, api_name: str, params: dict[str, Any], output_name: str) -> Path:
        """调用指定天眼查 API。"""
        call_data_source_tool = _get_data_source_tool()

        path = self._save_path(output_name)
        call_data_source_tool(
            data_source_name="tianyancha",
            api_name="tianyancha_api_call",
            params={"api_call_name": api_name, "api_call_params": params, "file_path": str(path)},
        )
        logger.info("Fetched Tianyancha %s -> %s", api_name, path)
        return path

    def fetch_base_info(self, company_name: str) -> Path:
        """获取企业基本信息。"""
        return self.call_api(
            api_name="工商信息-企业基本信息",
            params={"keyword": company_name},
            output_name=f"{company_name}_base_info.csv",
        )

    def fetch_historical_holders(self, company_name: str) -> Path:
        """获取历史股东信息。"""
        return self.call_api(
            api_name="工商信息-历史股东信息",
            params={"keyword": company_name, "pageSize": 10, "pageNum": 1},
            output_name=f"{company_name}_historical_holders.csv",
        )
