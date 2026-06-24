#!/usr/bin/env python3
"""plan-review skill 的离线 mock 生成器。

从 stdin 读取 JSON context，输出符合 skills/plan-review/SKILL.md 的复核草案。
主要用于 CI、离线环境或 Kimi CLI 不可用时。
"""

import json
import sys
from pathlib import Path


def _fallback_fixture() -> dict:
    """当 stdin 没有提供 context 时，读取测试 fixture。"""
    fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "plan_review_draft.json"
    if fixture.exists():
        return json.loads(fixture.read_text(encoding="utf-8"))
    return {
        "triggered_conditions": ["mock: 无可用 context"],
        "deviations": ["mock: 使用默认复核草案"],
        "recommendation": "mock: 继续持有观察",
        "suggested_action": "mock: 暂无操作",
        "fundamental_review": "mock: 基本面复核占位",
        "valuation_review": "mock: 估值复核占位",
        "market_review": "mock: 市场复核占位",
        "bull_arguments": [],
        "bear_arguments": [],
        "plan_change_suggestions": [],
    }


def main() -> None:
    context: dict = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                context = json.loads(raw)
        except json.JSONDecodeError:
            pass

    plan = context.get("plan", {})
    ticker = plan.get("ticker", "UNKNOWN")
    triggered = context.get("deviation_result", {}).get("triggered_conditions", [])

    if not context:
        output = _fallback_fixture()
    else:
        output = {
            "triggered_conditions": triggered,
            "deviations": [
                f"mock: {ticker} 触发 {len(triggered)} 项偏离条件" if triggered else "mock: 当前无明显偏离"
            ],
            "recommendation": "mock: 建议维持现有计划并持续观察",
            "suggested_action": "mock: 触发条件出现时再复核",
            "fundamental_review": f"mock: {ticker} 基本面复核占位",
            "valuation_review": f"mock: {ticker} 估值复核占位",
            "market_review": f"mock: {ticker} 市场复核占位",
            "bull_arguments": ["mock: 多头论点占位"],
            "bear_arguments": ["mock: 空头论点占位"],
            "plan_change_suggestions": ["mock: 计划变更建议占位"],
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
