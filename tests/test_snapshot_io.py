"""Snapshot IO helpers 测试。"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.common.models import MarketSnapshot, PortfolioSnapshot, SourceMetadata
from src.common.snapshot_io import latest_snapshot_path, read_snapshot, write_snapshot


def test_write_snapshot_versioned_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.common.snapshot_io.settings.project_root", tmp_path)
    snapshot = MarketSnapshot(
        snapshot_id="market-test",
        version="20260623120000-abc123",
        trade_date=__import__("datetime").date(2026, 6, 23),
        metadata=SourceMetadata(source="test", retrieved_at=datetime.now()),
    )
    path = write_snapshot(snapshot, "market", use_version_dir=True)
    assert path == tmp_path / "data" / "reports" / "market" / "20260623120000-abc123" / "snapshot.json"
    assert path.exists()
    loaded = read_snapshot(path, MarketSnapshot)
    assert loaded.snapshot_id == snapshot.snapshot_id


def test_latest_snapshot_path_sorts_by_version_not_mtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.common.snapshot_io.settings.project_root", tmp_path)
    older = MarketSnapshot(
        snapshot_id="market-older",
        version="20260623100000-old001",
        trade_date=__import__("datetime").date(2026, 6, 23),
        metadata=SourceMetadata(source="test", retrieved_at=datetime.now()),
    )
    newer = MarketSnapshot(
        snapshot_id="market-newer",
        version="20260623120000-new001",
        trade_date=__import__("datetime").date(2026, 6, 23),
        metadata=SourceMetadata(source="test", retrieved_at=datetime.now()),
    )
    older_path = write_snapshot(older, "market", use_version_dir=True)
    newer_path = write_snapshot(newer, "market", use_version_dir=True)

    # 让旧文件的 mtime 比新文件更晚，验证按版本排序
    now = datetime.now().timestamp()
    older_path.touch()
    older_path.parent.touch()
    older_path.parent.touch()

    latest = latest_snapshot_path("market")
    assert latest is not None
    assert latest.parent.name == "20260623120000-new001"


def test_write_snapshot_rejects_unsupported_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.common.snapshot_io.settings.project_root", tmp_path)
    snapshot = PortfolioSnapshot(
        snapshot_id="portfolio-test",
        version="20260623120000-abc123",
        metadata=SourceMetadata(source="test", retrieved_at=datetime.now()),
    )
    with pytest.raises(ValueError, match="Unsupported snapshot suffix"):
        write_snapshot(snapshot, "portfolio", suffix="md")


def test_latest_snapshot_path_returns_none_when_no_snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.common.snapshot_io.settings.project_root", tmp_path)
    assert latest_snapshot_path("nonexistent") is None
