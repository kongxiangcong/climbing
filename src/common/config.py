"""项目配置加载。"""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """返回项目根目录。"""
    return Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _interpolate_env(value: Any, env: dict[str, str]) -> Any:
    """递归替换 ${VAR} 形式的环境变量。"""
    if isinstance(value, str):
        for key, val in env.items():
            value = value.replace(f"${{{key}}}", val)
        return value
    if isinstance(value, dict):
        return {k: _interpolate_env(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v, env) for v in value]
    return value


class Settings(BaseSettings):
    """全局配置对象。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "Climbing"
    project_version: str = "0.1.0"

    # 路径
    project_root: Path = Field(default_factory=get_project_root)

    # YAML 配置内容
    _raw_config: dict[str, Any] = {}

    def __init__(self, **values: Any):
        super().__init__(**values)
        self._load_config()

    def _load_config(self) -> None:
        env = dict(os.environ)
        env["PROJECT_ROOT"] = str(self.project_root)

        config_path = self.project_root / "config" / "settings.yaml"
        raw = _load_yaml(config_path)
        self._raw_config = _interpolate_env(raw, env)

        self.project_name = self._raw_config.get("project", {}).get("name", self.project_name)
        self.project_version = self._raw_config.get("project", {}).get("version", self.project_version)

    def get(self, key: str, default: Any = None) -> Any:
        """通过点号路径获取配置项，如 data_sources.stock_finance_data.enabled。"""
        keys = key.split(".")
        value = self._raw_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def raw_config(self) -> dict[str, Any]:
        return self._raw_config


settings = Settings()
