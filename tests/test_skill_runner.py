"""Kimi CLI skill runner 测试。"""

import shutil

import pytest

from src.common.skill_runner import SkillRunner, run_skill


@pytest.mark.skipif(
    not shutil.which("kimi"),
    reason="Kimi CLI not installed",
)
class TestSkillRunner:
    def test_find_builtin_kimi_datasource_dir(self) -> None:
        path = SkillRunner.find_builtin_skill_dir("kimi-datasource")
        assert path is not None
        assert (path / "SKILL.md").exists()

    def test_run_builtin_skill_smoke(self) -> None:
        """使用内置 kimi-datasource skill 查询股价，验证 Kimi CLI 可连通。"""
        result = run_skill(
            prompt="请使用 stock_finance_data 查询 000725.SZ 当前股价，只返回一行结果",
            skill_name="kimi-datasource",
            timeout=120,
        )
        # 即使业务返回错误，也应能拿到结构化输出
        assert "returncode" in result
        assert "stdout" in result
        assert "stderr" in result
        assert result["parsed_output"] is not None
        # 成功时应包含 assistant 的最终回答
        if result["returncode"] == 0:
            parsed = result["parsed_output"]
            assert isinstance(parsed, list)
            contents = [
                record.get("content", "")
                for record in parsed
                if isinstance(record, dict) and record.get("role") == "assistant" and "content" in record
            ]
            assert any("000725" in c for c in contents) or "000725" in result["stdout"]
