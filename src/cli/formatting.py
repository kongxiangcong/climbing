"""CLI 输出格式化 helpers。"""

import json
from enum import Enum
from pathlib import Path
from typing import Any

import typer


class OutputFormat(str, Enum):
    """CLI 输出格式。"""

    TEXT = "text"
    JSON = "json"


def format_result(
    ctx: typer.Context | None,
    success: bool,
    message: str,
    snapshot_path: Path | str | None = None,
    version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """统一输出 CLI 结果。

    当 ``--format json`` 时输出结构化 JSON，供 agent 调用；否则输出人类可读文本。
    """
    fmt = OutputFormat.TEXT
    if ctx is not None and ctx.obj:
        fmt = OutputFormat(ctx.obj.get("format", "text"))

    result: dict[str, Any] = {
        "success": success,
        "message": message,
    }
    if snapshot_path is not None:
        result["snapshot_path"] = str(snapshot_path)
    if version is not None:
        result["version"] = version
    if extra:
        result.update(extra)

    if fmt == OutputFormat.JSON:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        typer.echo(message)
        if snapshot_path:
            typer.echo(f"Snapshot: {snapshot_path}")
        if version:
            typer.echo(f"Version: {version}")
