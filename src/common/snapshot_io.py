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
    use_version_dir: bool = False,
) -> Path:
    """将 Pydantic snapshot 写入磁盘，返回文件路径。

    当 ``use_version_dir=True`` 时，写入 ``data/reports/{report_type}/{version}/snapshot.{suffix}``，
    用于 MarketSnapshot 等需要按版本目录组织的快照。

    当前仅支持 ``suffix="json"``；其他格式会在实现后开放。
    """
    if suffix != "json":
        raise ValueError(f"Unsupported snapshot suffix: {suffix!r}; only 'json' is supported")
    if use_version_dir:
        path = get_snapshot_dir(report_type) / snapshot.version / f"snapshot.{suffix}"
    else:
        path = get_snapshot_dir(report_type, ticker) / f"{snapshot.version}.{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = snapshot.model_dump(mode="json")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    logger.info("Wrote %s snapshot -> %s", report_type, path)
    return path


def read_snapshot(path: Path, model_class: type[T]) -> T:
    """从磁盘读取 snapshot 并校验 schema。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return model_class.model_validate(data)


def _version_sort_key(path: Path) -> str:
    """从路径中提取版本排序键。

    兼容：
    - ``data/reports/{report_type}/{version}.json`` → ``version``
    - ``data/reports/{report_type}/{version}/snapshot.json`` → ``version``
    """
    if path.name == "snapshot.json":
        return path.parent.name
    return path.stem


def latest_snapshot_path(report_type: str, ticker: str | None = None) -> Path | None:
    """返回某类快照中最新的一份；若不存在返回 None。

    兼容两种目录结构：
    - ``data/reports/{report_type}/{version}.json``
    - ``data/reports/{report_type}/{version}/snapshot.json``

    按版本字符串倒序排列（版本以 ``YYYYMMDDhhmmss`` 开头）。
    """
    path = get_snapshot_dir(report_type, ticker)
    if not path.exists():
        return None

    candidates: list[Path] = []
    # 直接子目录下的 snapshot.json
    candidates.extend(path.glob("*/snapshot.json"))
    # 直接位于 report_type 目录下的 *.json
    candidates.extend(path.glob("*.json"))

    files = sorted(candidates, key=_version_sort_key, reverse=True)
    return files[0] if files else None


def _json_default(obj: object) -> str:
    """处理 datetime / Decimal 等不可序列化类型。"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
