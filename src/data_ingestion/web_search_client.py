"""网络搜索客户端封装。"""

from src.common.config import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


class WebSearchClient:
    """WebSearch / FetchURL 封装。"""

    def __init__(self) -> None:
        self.enabled = settings.get("data_sources.web_search.enabled", True)

    def search(self, query: str, limit: int = 5, include_content: bool = False) -> dict:
        """执行网络搜索。仅在 Kimi Code 运行时环境中可用。"""
        try:
            from tools import WebSearch

            result = WebSearch(query=query, limit=limit, include_content=include_content)
            logger.info("Web searched '%s'", query)
            return result
        except ImportError:
            logger.warning("WebSearch tool not available in local environment")
            return {"query": query, "results": [], "note": "local_placeholder"}

    def fetch_url(self, url: str) -> dict:
        """抓取指定 URL 内容。仅在 Kimi Code 运行时环境中可用。"""
        try:
            from tools import FetchURL

            result = FetchURL(url=url)
            logger.info("Fetched URL %s", url)
            return result
        except ImportError:
            logger.warning("FetchURL tool not available in local environment")
            return {"url": url, "content": "", "note": "local_placeholder"}
