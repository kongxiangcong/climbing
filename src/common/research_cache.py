"""个股研报三级缓存逻辑。"""

from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import ResearchSnapshot
from src.common.snapshot_io import latest_snapshot_path, read_snapshot

logger = get_logger(__name__)


class CacheTier(str, Enum):
    """研报缓存层级。"""

    NON_EXISTENT = "non_existent"
    STALE = "stale"
    MINOR_REFRESH = "minor_refresh"
    FRESH = "fresh"


class ResearchCache:
    """按 ticker 维护研报缓存状态。

    判断规则（按优先级）：
    1. 无 snapshot -> NON_EXISTENT
    2. 读取失败 -> NON_EXISTENT
    3. 超过 TTL 或 next_earnings_date 已至 -> STALE
    4. 检测到财报/公告/监管事件 -> STALE（当前 stub，预留扩展点）
    5. 仅价格/估值变化 -> MINOR_REFRESH（当前 stub，预留扩展点）
    6. 否则 -> FRESH
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def latest_snapshot_path(self) -> Path | None:
        return latest_snapshot_path("equity", self.ticker)

    def determine_tier(self) -> tuple[CacheTier, ResearchSnapshot | None]:
        path = self.latest_snapshot_path()
        if path is None:
            logger.debug("No existing research snapshot for %s", self.ticker)
            return CacheTier.NON_EXISTENT, None

        try:
            snapshot = read_snapshot(path, ResearchSnapshot)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load research snapshot for %s: %s", self.ticker, exc)
            return CacheTier.NON_EXISTENT, None

        if self._is_expired(snapshot):
            logger.debug("Research snapshot for %s is expired", self.ticker)
            return CacheTier.STALE, snapshot

        if self._has_earnings_event(snapshot):
            logger.debug("Research snapshot for %s has earnings event", self.ticker)
            return CacheTier.STALE, snapshot

        if self._has_announcement_event(snapshot):
            logger.debug("Research snapshot for %s has announcement event", self.ticker)
            return CacheTier.STALE, snapshot

        if self._has_regulatory_event(snapshot):
            logger.debug("Research snapshot for %s has regulatory event", self.ticker)
            return CacheTier.STALE, snapshot

        if self._only_price_valuation_changed(snapshot):
            logger.debug("Research snapshot for %s needs minor refresh", self.ticker)
            return CacheTier.MINOR_REFRESH, snapshot

        return CacheTier.FRESH, snapshot

    def _is_expired(self, snapshot: ResearchSnapshot) -> bool:
        ttl_days = settings.get("research.snapshot_ttl_days", 7)
        if not isinstance(ttl_days, int):
            ttl_days = int(ttl_days)
        age = datetime.now() - snapshot.created_at
        return age > timedelta(days=ttl_days)

    def _has_earnings_event(self, snapshot: ResearchSnapshot) -> bool:
        if (
            snapshot.research_metadata
            and snapshot.research_metadata.next_earnings_date
        ):
            return snapshot.research_metadata.next_earnings_date <= date.today()
        return False

    def _has_announcement_event(self, snapshot: ResearchSnapshot) -> bool:  # noqa: ARG002
        """检测重大公告事件。当前无实时公告源，预留扩展点。"""
        return False

    def _has_regulatory_event(self, snapshot: ResearchSnapshot) -> bool:  # noqa: ARG002
        """检测监管事件。当前无实时监管数据源，预留扩展点。"""
        return False

    def _only_price_valuation_changed(self, snapshot: ResearchSnapshot) -> bool:  # noqa: ARG002
        """判断是否只有价格/估值发生变化。当前无实时行情源，预留扩展点。"""
        return False

    # -----------------------------------------------------------------------
    # 可覆盖的扩展点，用于测试与后续接入真实数据源
    # -----------------------------------------------------------------------

    def _announcement_events_since(self, since: datetime) -> list[dict[str, Any]]:
        """返回自 since 以来的重大公告列表；子类/外部可注入。"""
        return []

    def _regulatory_events_since(self, since: datetime) -> list[dict[str, Any]]:
        """返回自 since 以来的监管事件列表；子类/外部可注入。"""
        return []

    def _current_stock_price_data(self) -> dict[str, Any] | None:
        """返回当前行情数据；子类/外部可注入。"""
        return None
