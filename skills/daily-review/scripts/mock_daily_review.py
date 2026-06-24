#!/usr/bin/env python3
"""daily-review skill 的离线 mock 生成器。

从 stdin 或文件读取 JSON context，输出符合 skills/daily-review/SKILL.md 的复盘草案。
主要用于 CI、离线环境或 Kimi CLI 不可用时。
"""

import json
import sys
from pathlib import Path


def _fallback_fixture() -> dict:
    """当没有可用 context 时，读取测试 fixture。"""
    fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "daily_review.json"
    if fixture.exists():
        return json.loads(fixture.read_text(encoding="utf-8"))
    return {
        "highlights": ["mock: 无可用 context"],
        "sentiment": "mock: 中性",
        "portfolio_risk": {"level": "low"},
        "plan_deviations": [],
        "stale_research": [],
        "watchlist": [],
    }


def generate_daily_review(context: dict) -> dict:
    """基于 context 生成 DailyReviewSnapshot 草案。"""
    market = context.get("market_snapshot", {}) or {}
    portfolio = context.get("portfolio_snapshot", {}) or {}
    deviations = context.get("plan_deviations", []) or []
    stale = context.get("stale_research", []) or []
    watchlist = context.get("watchlist", []) or []

    risk_appetite = market.get("risk_appetite") or "中性"
    indices = market.get("indices", []) or []
    positions = portfolio.get("positions", []) or []

    highlights = [
        f"市场整体情绪：{risk_appetite}，覆盖 {len(indices)} 只核心指数。",
        f"当前持仓标的：{len(positions)} 只。",
    ]
    if deviations:
        highlights.append(f"发现 {len(deviations)} 条交易计划偏离，需要复核。")
    if stale:
        highlights.append(f"发现 {len(stale)} 只股票的研究快照过期，建议重跑研报。")
    if watchlist:
        highlights.append(f"明日关注清单包含 {len(watchlist)} 只标的。")

    portfolio_risk = {
        "level": portfolio.get("max_drawdown") or "low",
        "concentration": (
            "持仓集中度正常" if len(positions) <= 3 else "持仓较分散，请检查重点标的"
        ),
        "position_count": len(positions),
        "unrealized_pnl": str(portfolio.get("unrealized_pnl", "0")),
    }

    return {
        "highlights": highlights,
        "sentiment": risk_appetite,
        "portfolio_risk": portfolio_risk,
        "plan_deviations": deviations,
        "stale_research": stale,
        "watchlist": watchlist,
    }


def main() -> None:
    context: dict = {}
    if len(sys.argv) < 2:
        if not sys.stdin.isatty():
            try:
                raw = sys.stdin.read()
                if raw.strip():
                    context = json.loads(raw)
            except json.JSONDecodeError:
                pass
    else:
        context = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    if not context:
        output = _fallback_fixture()
    else:
        output = generate_daily_review(context)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
