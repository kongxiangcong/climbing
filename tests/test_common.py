"""测试公共模块。"""

from src.common.config import settings
from src.common.paths import get_project_root


def test_settings_load() -> None:
    assert settings.project_name == "Climbing"
    assert settings.project_version == "0.1.0"


def test_project_root() -> None:
    root = get_project_root()
    assert (root / "config" / "settings.yaml").exists()
