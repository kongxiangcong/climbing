"""Mock trade-plan skill: generate a draft TradePlan JSON from context.

This script is used in CI / offline environments where Kimi CLI is unavailable.
It reads a ResearchSnapshot JSON and produces a deterministic draft plan.
"""

import json
import sys
from pathlib import Path
from typing import Any


def _decimal_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def generate_draft(context: dict[str, Any]) -> dict[str, Any]:
    """Generate a draft TradePlan dict from context."""
    research = context.get("research_snapshot", {})
    ticker = research.get("ticker", "UNKNOWN")
    research_version = research.get("version", "unknown")
    summary = research.get("summary", "")
    target_low = research.get("target_price_low")
    target_high = research.get("target_price_high")
    invalidation = research.get("invalidation_conditions", [])
    assumptions = research.get("assumptions", [])

    stock_price = research.get("stock_price_data", {}) or {}
    current_price = stock_price.get("current_price")

    # Deterministic fallback values
    if target_low is None and current_price is not None:
        target_low = round(float(current_price) * 1.05, 2)
    if target_high is None and current_price is not None:
        target_high = round(float(current_price) * 1.25, 2)

    stop_loss = None
    if current_price is not None:
        stop_loss = round(float(current_price) * 0.92, 2)

    return {
        "name": f"{ticker} 交易计划",
        "direction": "long",
        "time_window": "3-6m",
        "research_version": research_version,
        "entry_logic": f"基于研报核心观点：{summary[:120]}",
        "exit_logic": "达到目标价区间上限或触发失效条件时退出",
        "target_price_low": target_low,
        "target_price_high": target_high,
        "stop_loss": stop_loss,
        "take_profit": target_high,
        "position_limit": 10,
        "initial_position_pct": 3,
        "max_position_pct": 10,
        "risk_budget": 2,
        "expected_return": 15,
        "invalidation_conditions": invalidation
        or [
            "核心假设被证伪",
            "股价跌破止损位",
        ],
        "alternative_scenarios": [
            "价格快速突破上限：考虑分批止盈",
            "行业景气度低于预期：减仓至观察仓位",
        ],
        "triggers": [
            "价格进入目标价区间下限",
            "财报验证核心假设",
            "板块热度持续处于前 20%",
        ],
        "batch_strategy": [
            {
                "batch_id": "1",
                "target_price_low": _decimal_str(target_low),
                "target_price_high": _decimal_str(
                    round((float(target_low) + float(target_high)) / 2, 2)
                    if target_low is not None and target_high is not None
                    else None
                ),
                "allocation_pct": "40",
                "trigger_condition": "价格进入目标区间且成交量放大",
                "notes": "首批建仓",
            },
            {
                "batch_id": "2",
                "target_price_low": _decimal_str(
                    round((float(target_low) + float(target_high)) / 2, 2)
                    if target_low is not None and target_high is not None
                    else None
                ),
                "target_price_high": _decimal_str(target_high),
                "allocation_pct": "60",
                "trigger_condition": "基本面催化剂兑现或价格突破中枢",
                "notes": "加仓至目标仓位",
            },
        ],
        "review_frequency": "weekly",
        "notes": "mock draft generated from research snapshot",
        "assumptions": assumptions[:3] if assumptions else [],
    }


def main() -> None:
    if len(sys.argv) < 2:
        # Read context from stdin
        context = json.load(sys.stdin)
    else:
        context = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    draft = generate_draft(context)
    print(json.dumps(draft, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
