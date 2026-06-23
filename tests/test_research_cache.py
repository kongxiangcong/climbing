"""ResearchCache 三级缓存逻辑测试。"""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.common.models import ResearchSnapshot, ResearchMetadata, SourceMetadata
from src.common.research_cache import CacheTier, ResearchCache
from src.common.snapshot_io import write_snapshot


@pytest.fixture
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """将项目根目录指向临时目录，避免污染真实 data/。"""
    monkeypatch.setattr("src.common.config.settings.project_root", tmp_path)
    return tmp_path


def _write_snapshot(
    project_root: Path,
    ticker: str,
    version: str,
    created_at: datetime,
    next_earnings_date: date | None = None,
) -> Path:
    metadata = ResearchMetadata(
        company_name="京东方 A",
        ticker=ticker,
        next_earnings_date=next_earnings_date,
    )
    snapshot = ResearchSnapshot(
        snapshot_id=f"research-{ticker}-{version}",
        report_type="research",
        version=version,
        ticker=ticker,
        summary="summary",
        research_metadata=metadata,
        metadata=SourceMetadata(source="test", retrieved_at=created_at),
        created_at=created_at,
    )
    # equity report 目录结构：data/reports/equity/{ticker}/{version}/snapshot.json
    report_dir = project_root / "data" / "reports" / "equity" / ticker / version
    report_dir.mkdir(parents=True)
    path = report_dir / "snapshot.json"
    path.write_text(
        snapshot.model_dump_json(indent=2, by_alias=True),
        encoding="utf-8",
    )
    return path


class _TestCache(ResearchCache):
    """可注入事件与价格信号的测试用缓存子类。"""

    def __init__(
        self,
        ticker: str,
        *,
        has_announcement: bool = False,
        has_regulatory: bool = False,
        price_changed: bool = False,
    ) -> None:
        super().__init__(ticker)
        self._has_announcement = has_announcement
        self._has_regulatory = has_regulatory
        self._price_changed = price_changed

    def _has_announcement_event(self, snapshot: ResearchSnapshot) -> bool:
        return self._has_announcement

    def _has_regulatory_event(self, snapshot: ResearchSnapshot) -> bool:
        return self._has_regulatory

    def _only_price_valuation_changed(self, snapshot: ResearchSnapshot) -> bool:
        return self._price_changed


def test_non_existent_tier(project_root: Path) -> None:
    cache = ResearchCache("NOTEXIST.SZ")
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.NON_EXISTENT
    assert snapshot is None


def test_fresh_snapshot(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-abc123",
        created_at=datetime.now() - timedelta(hours=1),
        next_earnings_date=date(2099, 12, 31),
    )
    cache = ResearchCache("000725.SZ")
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.FRESH
    assert snapshot is not None
    assert snapshot.ticker == "000725.SZ"


def test_stale_due_to_ttl(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260601120000-abc123",
        created_at=datetime.now() - timedelta(days=30),
        next_earnings_date=date(2099, 12, 31),
    )
    cache = ResearchCache("000725.SZ")
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.STALE
    assert snapshot is not None


def test_stale_due_to_earnings_date(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-abc123",
        created_at=datetime.now() - timedelta(hours=1),
        next_earnings_date=date(2020, 1, 1),
    )
    cache = ResearchCache("000725.SZ")
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.STALE
    assert snapshot is not None


def test_stale_due_to_announcement(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-abc123",
        created_at=datetime.now() - timedelta(hours=1),
        next_earnings_date=date(2099, 12, 31),
    )
    cache = _TestCache("000725.SZ", has_announcement=True)
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.STALE


def test_stale_due_to_regulatory_event(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-abc123",
        created_at=datetime.now() - timedelta(hours=1),
        next_earnings_date=date(2099, 12, 31),
    )
    cache = _TestCache("000725.SZ", has_regulatory=True)
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.STALE


def test_minor_refresh_tier(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-abc123",
        created_at=datetime.now() - timedelta(hours=1),
        next_earnings_date=date(2099, 12, 31),
    )
    cache = _TestCache("000725.SZ", price_changed=True)
    tier, snapshot = cache.determine_tier()
    assert tier == CacheTier.MINOR_REFRESH
    assert snapshot is not None


def test_latest_snapshot_path_returns_newest_version(project_root: Path) -> None:
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260622120000-old",
        created_at=datetime.now() - timedelta(days=1),
    )
    _write_snapshot(
        project_root,
        "000725.SZ",
        "20260623120000-new",
        created_at=datetime.now(),
    )
    cache = ResearchCache("000725.SZ")
    latest = cache.latest_snapshot_path()
    assert latest is not None
    assert latest.parent.name == "20260623120000-new"
