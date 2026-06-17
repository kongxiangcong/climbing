"""项目路径管理。"""

from pathlib import Path

from src.common.config import settings


def get_project_root() -> Path:
    """返回项目根目录。"""
    return settings.project_root


def get_data_dir(subdir: str | None = None) -> Path:
    """返回数据目录，可选子目录。"""
    path = settings.project_root / "data"
    if subdir:
        path = path / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    """返回配置目录。"""
    return settings.project_root / "config"


def get_report_template_dir() -> Path:
    """返回报告模板目录。"""
    return settings.project_root / "src" / "report_generation" / "templates"
