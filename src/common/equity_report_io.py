"""Equity report 版本化目录与多文件写入 helpers。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_equity_report_dir(ticker: str, version: str) -> Path:
    """创建并返回 ``data/reports/equity/{ticker}/{version}/`` 目录。"""
    path = settings.project_root / "data" / "reports" / "equity" / ticker / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def _minimal_pdf_bytes(text: str = "Placeholder PDF") -> bytes:
    """生成一个最小但有效的 PDF 字节串（占位用）。"""
    objects: list[str] = []

    def add_obj(content: str) -> int:
        idx = len(objects) + 1
        objects.append(f"{idx} 0 obj\n{content}\nendobj\n")
        return idx

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    add_obj("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")

    stream = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET"
    add_obj(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    add_obj(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    body = b"%PDF-1.4\n"
    offsets: list[int] = [0]  # object 0 is free
    for obj in objects:
        offsets.append(len(body))
        body += obj.encode("latin-1")

    xref_offset = len(body)
    xref = f"xref\n0 {len(offsets)}\n"
    xref += "0000000000 65535 f \n"
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n"

    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    body += trailer.encode("latin-1")
    return body


def write_equity_report_files(
    report_dir: Path,
    snapshot: dict[str, Any],
    qa_check: dict[str, Any],
    references: list[dict[str, Any]],
    pdf_path: Path | None = None,
) -> dict[str, Path]:
    """将 equity report 的四个标准文件写入目录。

    Args:
        report_dir: 版本化报告目录，已存在。
        snapshot: 已序列化为 dict 的 ResearchSnapshot。
        qa_check: QA 结果 dict。
        references: 引用列表。
        pdf_path: 已生成的 PDF 路径；若为 None 则写入占位 PDF。

    Returns:
        文件名到路径的映射。
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = report_dir / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    qa_path = report_dir / "qa_check.json"
    qa_path.write_text(
        json.dumps(qa_check, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    refs_path = report_dir / "references.json"
    refs_path.write_text(
        json.dumps(references, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    target_pdf = report_dir / "report.pdf"
    if pdf_path is not None and pdf_path.exists() and pdf_path != target_pdf:
        import shutil

        shutil.copy2(pdf_path, target_pdf)
    elif not target_pdf.exists():
        target_pdf.write_bytes(_minimal_pdf_bytes())

    logger.info("Wrote equity report files to %s", report_dir)
    return {
        "snapshot": snapshot_path,
        "qa_check": qa_path,
        "references": refs_path,
        "report_pdf": target_pdf,
    }


def build_qa_check(passed: bool = True, issues: list[str] | None = None) -> dict[str, Any]:
    """构造最小 QA 检查结果。"""
    return {
        "checks_passed": passed,
        "issues": issues or [],
        "checked_at": datetime.now().isoformat(),
    }
