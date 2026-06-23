"""Equity report 生成与目录结构测试。"""

import json
from pathlib import Path
from typing import Any

import pytest

from src.common.config import settings
from src.common.equity_report_io import (
    build_qa_check,
    get_equity_report_dir,
    write_equity_report_files,
)
from src.report_generation.equity_report import EquityReportGenerator


@pytest.fixture
def tmp_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """将项目根目录指向临时目录，避免污染真实 data/。"""
    monkeypatch.setattr("src.common.equity_report_io.settings.project_root", tmp_path)
    monkeypatch.setattr("src.report_generation.equity_report.settings.project_root", tmp_path)
    return tmp_path


def test_get_equity_report_dir_creates_versioned_path(
    tmp_project_root: Path,
) -> None:
    version = "20260623120000-abc123"
    path = get_equity_report_dir("000725.SZ", version)
    assert path == tmp_project_root / "data" / "reports" / "equity" / "000725.SZ" / version
    assert path.exists()


def test_write_equity_report_files_creates_all_files(
    tmp_project_root: Path,
) -> None:
    report_dir = tmp_project_root / "data" / "reports" / "equity" / "000725.SZ" / "v1"
    report_dir.mkdir(parents=True)

    snapshot: dict[str, Any] = {
        "ticker": "000725.SZ",
        "version": "v1",
        "report_type": "research",
    }
    qa: dict[str, Any] = {"checks_passed": True, "issues": []}
    refs: list[dict[str, Any]] = [{"title": "年报", "url": ""}]

    result = write_equity_report_files(report_dir, snapshot, qa, refs)

    assert result["snapshot"].exists()
    assert result["qa_check"].exists()
    assert result["references"].exists()
    assert result["report_pdf"].exists()

    loaded_snapshot = json.loads(result["snapshot"].read_text(encoding="utf-8"))
    assert loaded_snapshot["ticker"] == "000725.SZ"

    pdf_bytes = result["report_pdf"].read_bytes()
    assert pdf_bytes.startswith(b"%PDF-1.4")


def test_build_qa_check() -> None:
    qa = build_qa_check(passed=True, issues=["issue"])
    assert qa["checks_passed"] is True
    assert qa["issues"] == ["issue"]
    assert "checked_at" in qa


def _setup_skill_files(project_root: Path) -> None:
    """在临时项目根目录下创建 skill 模板与 CSS。"""
    template_dir = project_root / "skills" / "stock-research" / "templates"
    template_dir.mkdir(parents=True)
    css_path = project_root / "skills" / "stock-research" / "output" / "report.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text("body { color: #333; }", encoding="utf-8")
    (template_dir / "report.html.j2").write_text(
        "<html><body><h1>{{ ticker }}</h1><p>{{ summary }}</p></body></html>",
        encoding="utf-8",
    )


def test_equity_report_generator_html(tmp_project_root: Path) -> None:
    _setup_skill_files(tmp_project_root)
    gen = EquityReportGenerator()
    output = tmp_project_root / "test.html"
    gen.generate_html(
        "000725.SZ",
        {"summary": "test summary"},
        output,
    )
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "000725.SZ" in content
    assert "test summary" in content


def test_equity_report_generator_pdf_placeholder(tmp_project_root: Path) -> None:
    _setup_skill_files(tmp_project_root)
    gen = EquityReportGenerator()
    html_path = tmp_project_root / "test.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    pdf_path = tmp_project_root / "test.pdf"

    result = gen.generate_pdf(html_path, pdf_path)
    assert result.exists()
    assert result.read_bytes().startswith(b"%PDF-1.4")


def test_equity_report_generator_report_data() -> None:
    snapshot: dict[str, Any] = {
        "ticker": "000725.SZ",
        "summary": "summary text",
        "valuation": {
            "method": "PE-band",
            "value_low": 4.5,
            "value_high": 6.0,
            "assumptions": ["assumption"],
        },
        "six_dimensions": {"industry": "panel"},
        "risks": ["risk"],
        "assumptions": ["assumption"],
        "invalidation_conditions": ["condition"],
        "references": [{"title": "年报"}],
    }
    gen = EquityReportGenerator()
    data = gen.generate_report_data(snapshot)
    assert data["summary"] == "summary text"
    assert data["valuation_method"] == "PE-band"
    assert data["target_low"] == "4.5"
    assert data["target_high"] == "6.0"
    assert data["risks"] == ["risk"]
