#!/usr/bin/env python3
"""capital-flow skill 的离线 mock 生成器。

从 stdin 或文件读取 CapitalFlowSnapshot JSON，输出 MacroReportSnapshot 叙事字段。
主要用于 CI、离线环境或 Kimi CLI 不可用时。
"""

import json
import sys
from pathlib import Path


QUESTIONS = [
    {
        "question_id": "Q1",
        "question": "M2扩张是否带来实体融资回暖？",
    },
    {
        "question_id": "Q2",
        "question": "政策指引方向是否明确？",
    },
    {
        "question_id": "Q3",
        "question": "居民资产是否向权益迁移？",
    },
    {
        "question_id": "Q4",
        "question": "无风险利率趋势如何？",
    },
]


def _fallback_fixture() -> dict:
    """当没有可用 context 时，读取测试 fixture 中的 narrative 占位。"""
    fixture = (
        Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "capital_flow.json"
    )
    if fixture.exists():
        data = json.loads(fixture.read_text(encoding="utf-8"))
        return {
            "summary": "基于 fixture 的宏观月报综合判断（mock）。",
            "four_questions": data.get("assessments", []),
            "outlook": "后续关注 M2、PMI 与沪深300走势。",
            "risks": [" fixture 数据可能不代表真实市场", "mock 输出仅供测试"],
            "recommendations": ["运行真实 skill 获取基于事实的月报"],
        }
    return {
        "summary": "mock：无可用 context。",
        "four_questions": [
            {
                "question_id": q["question_id"],
                "question": q["question"],
                "answer": "mock：请补充分析。",
                "evidence": [],
                "label": "neutral",
            }
            for q in QUESTIONS
        ],
        "outlook": "mock：请补充展望。",
        "risks": ["mock：数据缺失"],
        "recommendations": ["mock：请运行真实 skill"],
    }


def _find_indicator(context: dict, name_substring: str) -> dict | None:
    for ind in context.get("indicators", []):
        if name_substring in ind.get("name", ""):
            return ind
    return None


def generate_macro_report(context: dict) -> dict:
    """基于 CapitalFlowSnapshot context 生成叙事草案。"""
    labels = {
        "growth": context.get("growth_label", "neutral"),
        "inflation": context.get("inflation_label", "neutral"),
        "liquidity": context.get("liquidity_label", "neutral"),
        "market_structure": context.get("market_structure_label", "neutral"),
    }
    m2 = _find_indicator(context, "M2")
    pmi = _find_indicator(context, "PMI")
    csi = _find_indicator(context, "沪深300")
    yield10 = _find_indicator(context, "10年期国债")

    summary_parts = [
        f"增长维度标记为 {labels['growth']}，通胀维度标记为 {labels['inflation']}。",
        f"流动性维度 {labels['liquidity']}，市场结构维度 {labels['market_structure']}。",
    ]
    if m2 and pmi:
        summary_parts.append(
            f"M2同比 {m2.get('value')}% 与 PMI {pmi.get('value')} 显示资金向实体传导效果一般。"
        )
    summary = " ".join(summary_parts)

    answers = {
        "Q1": (
            f"M2同比 {m2.get('value')}%，PMI {pmi.get('value') if pmi else '未知'}，"
            f"实体融资回暖程度判断为 {labels['liquidity']}。"
        ),
        "Q2": "货币政策维持稳健，财政政策通过专项债托底，方向相对明确。",
        "Q3": (
            f"沪深300 {'同比下跌' if csi and csi.get('yoy_change', 0) < 0 else '走势平稳'}，"
            f"居民风险偏好尚未明显回升。"
        ),
        "Q4": (
            f"10年期国债收益率 {yield10.get('value') if yield10 else '未知'}%，"
            f"处于历史偏低区间。"
        ),
    }

    four_questions = []
    for q in QUESTIONS:
        qid = q["question_id"]
        four_questions.append(
            {
                "question_id": qid,
                "question": q["question"],
                "answer": answers[qid],
                "evidence": [],
                "label": labels["liquidity"]
                if qid in ("Q1", "Q4")
                else labels["market_structure"]
                if qid == "Q3"
                else "neutral",
            }
        )

    return {
        "summary": summary,
        "four_questions": four_questions,
        "outlook": "短期内宏观环境以稳为主，关注政策落地与权益资金流向。",
        "risks": [
            "M2 增速持续偏低可能压制信用扩张",
            "PMI 低于荣枯线反映内需偏弱",
            "沪深300走弱或拖累居民风险偏好",
        ],
        "recommendations": [
            "维持防御性仓位，关注高股息与现金流稳定品种",
            "跟踪社融与 PMI 数据变化",
            "若流动性标签转暖再提升权益暴露",
        ],
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
        output = generate_macro_report(context)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
