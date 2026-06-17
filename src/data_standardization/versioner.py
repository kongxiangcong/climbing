"""版本化与快照管理。"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.paths import get_data_dir


def generate_version(input_data: Any | None = None) -> str:
    """生成版本号：时间戳 + 可选内容哈希前6位。"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    if input_data is None:
        return ts
    if isinstance(input_data, str):
        data_str = input_data
    else:
        data_str = str(input_data)
    hash_prefix = hashlib.sha256(data_str.encode("utf-8")).hexdigest()[:6]
    return f"{ts}-{hash_prefix}"


def snapshot_path(report_type: str, ticker: str | None, version: str) -> Path:
    """生成报告快照路径。"""
    reports_dir = get_data_dir("reports")
    if ticker:
        path = reports_dir / report_type / ticker
    else:
        path = reports_dir / report_type
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{version}.md"


def cleanup_old_snapshots(report_type: str, ticker: str | None = None, keep: int | None = None) -> None:
    """清理旧快照，保留最近 N 个。"""
    keep = keep or settings.get("reports.keep_snapshots", 30)
    reports_dir = get_data_dir("reports")
    if ticker:
        path = reports_dir / report_type / ticker
    else:
        path = reports_dir / report_type

    if not path.exists():
        return

    files = sorted(path.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old_file in files[keep:]:
        old_file.unlink()
