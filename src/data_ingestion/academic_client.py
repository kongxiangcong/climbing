"""学术数据源客户端（arXiv + Scholar）。"""

from pathlib import Path

from src.common.config import settings
from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class AcademicClient:
    """学术搜索客户端。"""

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = raw_dir or get_data_dir("raw") / "academic"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = settings.get("data_sources.arxiv.enabled", True)

    def _save_path(self, name: str) -> Path:
        return self.raw_dir / name

    def search_arxiv(self, query: str, max_results: int = 10) -> Path:
        """搜索 arXiv 论文。"""
        from mcp__plugin-kimi-datasource_data import call_data_source_tool

        path = self._save_path(f"arxiv_{query.replace(' ', '_')}.csv")
        call_data_source_tool(
            data_source_name="arxiv",
            api_name="search_papers",
            params={"query": query, "max_results": max_results, "file_path": str(path)},
        )
        logger.info("Searched arXiv for '%s' -> %s", query, path)
        return path

    def search_scholar(self, query: str, num_results: int = 10) -> Path:
        """搜索 Google Scholar 论文。"""
        from mcp__plugin-kimi-datasource_data import call_data_source_tool

        path = self._save_path(f"scholar_{query.replace(' ', '_')}.csv")
        call_data_source_tool(
            data_source_name="scholar",
            api_name="scholar_search",
            params={"query": query, "num_results": num_results, "file_path": str(path)},
        )
        logger.info("Searched Scholar for '%s' -> %s", query, path)
        return path
