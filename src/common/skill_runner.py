"""统一 Kimi CLI skill 调用封装。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

from src.common.config import settings
from src.common.logger import get_logger
from src.common.paths import get_data_dir

logger = get_logger(__name__)


class SkillRunnerError(Exception):
    """Skill 调用异常。"""


class SkillRunner:
    """封装 Kimi CLI 调用：构造命令、传递参数与上下文、等待完成、捕获输出。"""

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self.kimi_bin = shutil.which("kimi") or "kimi"

    @staticmethod
    def find_builtin_skill_dir(skill_name: str) -> Path | None:
        """查找 Kimi Code 内置 plugin skill 目录。"""
        home = Path.home() / ".kimi-code" / "plugins" / "managed" / skill_name
        if (home / "SKILL.md").exists():
            return home
        return None

    @staticmethod
    def find_project_skill_dir(skill_name: str) -> Path | None:
        """查找项目本地 skills/ 目录。"""
        path = settings.project_root / "skills" / skill_name
        if (path / "SKILL.md").exists():
            return path
        return None

    def run(
        self,
        prompt: str,
        skill_name: str | None = None,
        skills_dir: str | Path | None = None,
        context: dict[str, Any] | None = None,
        output_dir: str | Path | None = None,
        output_format: str = "stream-json",
        timeout: int = 300,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """调用 Kimi CLI 并返回结构化结果。

        Args:
            prompt: 发送给 skill 的用户提示。
            skill_name: 使用的 skill 名称；会优先从项目 skills/ 或内置 plugin 目录查找。
            skills_dir: 显式指定 skill 目录；若提供则覆盖 skill_name 的自动查找。
            context: 需要追加到 prompt 的上下文数据（会被 JSON 序列化）。
            output_dir: 期望 skill 写入产物的目录；仅作为提示附加到 prompt。
            output_format: Kimi CLI 输出格式，默认 stream-json。
            timeout: 子进程超时秒数。
            extra_args: 额外的 Kimi CLI 参数。
        """
        resolved_skills_dir = self._resolve_skills_dir(skill_name, skills_dir)
        full_prompt = self._build_prompt(prompt, context, output_dir)

        cmd: list[str] = [self.kimi_bin]
        if resolved_skills_dir:
            cmd.extend(["--skills-dir", str(resolved_skills_dir)])
        cmd.extend(["--prompt", full_prompt, "--output-format", output_format])
        if extra_args:
            cmd.extend(extra_args)
        cmd.extend(["--add-dir", str(settings.project_root)])

        logger.info("Running Kimi CLI: %s", " ".join(cmd))
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SkillRunnerError(f"Kimi CLI timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise SkillRunnerError(f"Kimi CLI not found: {self.kimi_bin}") from exc

        parsed_output = self._parse_output(proc.stdout, output_format)
        result: dict[str, Any] = {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "parsed_output": parsed_output,
        }
        if proc.returncode != 0:
            result["success"] = False
            logger.error("Kimi CLI failed: %s", proc.stderr)
        return result

    def _resolve_skills_dir(
        self,
        skill_name: str | None,
        skills_dir: str | Path | None,
    ) -> Path | None:
        if skills_dir:
            return Path(skills_dir)
        if skill_name:
            project_dir = self.find_project_skill_dir(skill_name)
            if project_dir:
                return project_dir
            builtin_dir = self.find_builtin_skill_dir(skill_name)
            if builtin_dir:
                return builtin_dir
            raise SkillRunnerError(f"Skill not found: {skill_name}")
        return self.skills_dir

    def _build_prompt(
        self,
        prompt: str,
        context: dict[str, Any] | None,
        output_dir: str | Path | None,
    ) -> str:
        parts = [prompt]
        if context:
            parts.append("\n\n[context]\n" + json.dumps(context, ensure_ascii=False, indent=2))
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            parts.append(f"\n\n[output_dir]\n{out_path.resolve()}")
        return "\n".join(parts)

    def _parse_output(
        self,
        stdout: str | None,
        output_format: str,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        if not stdout:
            return None
        if output_format == "stream-json":
            records: list[dict[str, Any]] = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # 非 JSON 行直接忽略；可后续扩展为原始文本
                    continue
            return records
        try:
            return cast(dict[str, Any], json.loads(stdout))
        except json.JSONDecodeError:
            return {"raw": stdout}


def run_skill(
    prompt: str,
    skill_name: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """便捷函数：直接调用 SkillRunner。"""
    return SkillRunner().run(prompt=prompt, skill_name=skill_name, **kwargs)
