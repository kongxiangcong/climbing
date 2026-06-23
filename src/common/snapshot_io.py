"""Snapshot 文件读写 helpers。"""

import json
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import Snapshot

logger = get_logger(__name__)

T = TypeVar("T", bound=Snapshot)


def get_snapshot_dir(report_type: str, ticker: str | None = None) -> Path:
    """返回快照目录并确保存在。"""
    reports_dir = settings.project_root / "data" / "reports"
    path = reports_dir / report_type
    if ticker:
        path = path / ticker
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_snapshot(
    snapshot: Snapshot,
    report_type: str,
    ticker: str | None = None,
    suffix: str = "json",
) -> Path:
    """将 Pydantic snapshot 写入磁盘，返回文件路径。"""
    path = get_snapshot_dir(report_type, ticker) / f"{snapshot.version}.{suffix}"
    data = snapshot.model_dump(mode="json")
    if suffix == "json":
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
    else:
        # 预留 markdown / 其他格式入口
        path.write_text(str(data), encoding="utf-8")
    logger.info("Wrote %s snapshot -> %s", report_type, path)
    return path


def read_snapshot(path: Path, model_class: type[T]) -> T:
    """从磁盘读取 snapshot 并校验 schema。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return model_class.model_validate(data)


def latest_snapshot_path(report_type: str, ticker: str | None = None) -> Path | None:
    """返回某类快照中最新的一份；若不存在返回 None。"""
    path = get_snapshot_dir(report_type, ticker)
    if not path.exists():
        return None
    files = sorted(path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _json_default(obj: object) -> str:
    """处理 datetime / Decimal 等不可序列化类型。"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
