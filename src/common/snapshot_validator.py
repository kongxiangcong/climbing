"""ResearchSnapshot 结构校验器。

由 equity-researcher/scripts/report_validator.py 适配而来：
- 原校验器检查 HTML 结构；
- 本校验器直接检查 ResearchSnapshot Pydantic 对象，确保其覆盖 13-section schema。
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.common.models import ResearchSnapshot


@dataclass
class CheckResult:
    """单项校验结果。"""

    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)


class SnapshotValidator:
    """校验 ResearchSnapshot 是否满足 equity-researcher 输出 schema 的结构要求。"""

    def __init__(self, snapshot: ResearchSnapshot) -> None:
        self.snapshot = snapshot
        self.results: list[CheckResult] = []

    def run_all(self) -> list[CheckResult]:
        self.check_metadata()
        self.check_core_narrative()
        self.check_six_dimensions()
        self.check_investment_logic()
        self.check_investment_thesis_table()
        self.check_company_overview()
        self.check_financial_data()
        self.check_valuation_data()
        self.check_catalyst_calendar()
        self.check_scenario_analysis()
        self.check_risks()
        self.check_industry_supply_chain()
        self.check_stock_price_data()
        return self.results

    @property
    def checks_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def issues(self) -> list[str]:
        return [r.message for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks_passed": self.checks_passed,
            "issues": self.issues,
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

    def check_metadata(self) -> None:
        meta = self.snapshot.research_metadata
        if meta is None:
            self.results.append(
                CheckResult(
                    "metadata",
                    False,
                    "缺少 research_metadata（Section I）",
                    ["必须包含公司名、市场、报告日期、最新财报期、基准指数等元数据"],
                )
            )
            return

        required = [
            ("company_name", meta.company_name),
            ("ticker", meta.ticker),
            ("market", meta.market),
            ("latest_financial_report", meta.latest_financial_report),
            ("benchmark_index", meta.benchmark_index),
        ]
        missing = [name for name, value in required if not value]
        passed = not missing
        self.results.append(
            CheckResult(
                "metadata",
                passed,
                "研报元数据完整" if passed else f"缺失元数据字段: {missing}",
                missing,
            )
        )

    def check_core_narrative(self) -> None:
        cn = self.snapshot.core_narrative
        if cn is not None and (cn.core_narrative or cn.core_viewpoint):
            self.results.append(
                CheckResult("core_narrative", True, "核心投资叙事非空")
            )
        elif self.snapshot.summary and "占位" not in self.snapshot.summary:
            self.results.append(
                CheckResult(
                    "core_narrative",
                    True,
                    "summary 作为核心叙事后向兼容",
                )
            )
        else:
            self.results.append(
                CheckResult(
                    "core_narrative",
                    False,
                    "核心投资叙事为空或仍为占位文本",
                    ["必须提供 core_narrative / core_viewpoint 或有效的 summary"],
                )
            )

    def check_six_dimensions(self) -> None:
        typed = self.snapshot.six_dimensions_typed
        loose = self.snapshot.six_dimensions

        if typed:
            conclusions = [d.conclusion for d in typed if d.conclusion]
            if len(conclusions) == 6:
                self.results.append(
                    CheckResult(
                        "six_dimensions",
                        True,
                        f"六维分析完整（{len(typed)} 个维度均有结论）",
                    )
                )
                return

        if isinstance(loose, dict) and len(loose) >= 6:
            self.results.append(
                CheckResult(
                    "six_dimensions",
                    True,
                    f"六维分析完整（{len(loose)} 个维度）",
                )
            )
            return

        self.results.append(
            CheckResult(
                "six_dimensions",
                False,
                "六维分析不完整",
                ["six_dimensions_typed 需包含 6 个带结论的维度，或 six_dimensions 字典包含至少 6 项"],
            )
        )

    def check_investment_logic(self) -> None:
        logic = self.snapshot.investment_logic
        if logic is None:
            self.results.append(
                CheckResult(
                    "investment_logic",
                    False,
                    "缺少 investment_logic（Section IV）",
                    ["必须包含 short_term / long_term 的多空因子"],
                )
            )
            return

        issues: list[str] = []
        for period in ("short_term", "long_term"):
            period_logic = getattr(logic, period)
            if not period_logic.bear_factors:
                issues.append(f"{period} 缺少 bear_factors（至少 1 个）")
            if not period_logic.bull_factors:
                issues.append(f"{period} 缺少 bull_factors（至少 1 个）")

        passed = not issues
        self.results.append(
            CheckResult(
                "investment_logic",
                passed,
                "投资逻辑多空因子完整" if passed else f"投资逻辑不完整: {issues}",
                issues,
            )
        )

    def check_investment_thesis_table(self) -> None:
        rows = self.snapshot.investment_thesis_table
        passed = len(rows) == 4
        self.results.append(
            CheckResult(
                "investment_thesis_table",
                passed,
                f"投资论点表包含 {len(rows)} 行" + ("（符合 4 行要求）" if passed else "（需要恰好 4 行）"),
                [] if passed else ["投资论点综合分析表必须包含 4 行（H1-H4）"],
            )
        )

    def check_company_overview(self) -> None:
        overview = self.snapshot.company_overview
        passed = overview is not None and overview.business_model is not None
        self.results.append(
            CheckResult(
                "company_overview",
                passed,
                "公司概览模块存在" if passed else "缺少 company_overview（Section VI）",
                [] if passed else ["必须包含 background / business_model / business_segments"],
            )
        )

    def check_financial_data(self) -> None:
        fin = self.snapshot.financial_data
        if fin is None:
            self.results.append(
                CheckResult(
                    "financial_data",
                    False,
                    "缺少 financial_data（Section VII）",
                    ["必须包含利润表、资产负债表、现金流量表亮点及关键比率"],
                )
            )
            return

        issues: list[str] = []
        if not fin.income_statement:
            issues.append("income_statement 为空")
        if not fin.key_ratios:
            issues.append("key_ratios 为空")
        if not fin.earnings_quality_signals:
            issues.append("earnings_quality_signals 为空")

        passed = not issues
        self.results.append(
            CheckResult(
                "financial_data",
                passed,
                "财务数据模块完整" if passed else f"财务数据不完整: {issues}",
                issues,
            )
        )

    def check_valuation_data(self) -> None:
        vd = self.snapshot.valuation_data
        valuation = self.snapshot.valuation
        if vd is not None and (vd.comparable_companies or vd.valuation_table):
            self.results.append(
                CheckResult("valuation_data", True, "估值数据模块存在")
            )
        elif valuation.method != "unknown":
            self.results.append(
                CheckResult(
                    "valuation_data",
                    True,
                    "基础 valuation 字段已提供（后向兼容）",
                )
            )
        else:
            self.results.append(
                CheckResult(
                    "valuation_data",
                    False,
                    "缺少估值数据（Section VIII）",
                    ["必须包含 valuation_data 或基础 valuation 字段"],
                )
            )

    def check_catalyst_calendar(self) -> None:
        events = self.snapshot.catalyst_calendar
        if len(events) < 4:
            self.results.append(
                CheckResult(
                    "catalyst_calendar",
                    False,
                    f"催化剂日历仅 {len(events)} 个事件（需 ≥4）",
                    ["必须包含至少 4 个催化剂事件"],
                )
            )
            return

        high_events = [e for e in events if e.importance == "High"]
        has_earnings = any(
            "earnings" in e.event.lower()
            or "财报" in e.event
            or (
                self.snapshot.research_metadata
                and self.snapshot.research_metadata.next_earnings_date
                and e.event_date == self.snapshot.research_metadata.next_earnings_date
            )
            for e in events
        )

        issues: list[str] = []
        if len(high_events) < 2:
            issues.append(f"High 重要性事件仅 {len(high_events)} 个（需 ≥2）")
        if not has_earnings:
            issues.append("催化剂日历未包含下次财报事件")

        passed = not issues
        self.results.append(
            CheckResult(
                "catalyst_calendar",
                passed,
                f"催化剂日历完整（{len(events)} 个事件，{len(high_events)} 个 High）"
                if passed
                else f"催化剂日历不完整: {issues}",
                issues,
            )
        )

    def check_scenario_analysis(self) -> None:
        scenarios = self.snapshot.scenario_analysis
        if not scenarios or "base_case" not in scenarios:
            self.results.append(
                CheckResult(
                    "scenario_analysis",
                    False,
                    "缺少情景分析 base_case（Section X）",
                    ["必须包含 optimistic / base_case / pessimistic 情景"],
                )
            )
            return

        total_prob = sum(s.probability for s in scenarios.values())
        prob_ok = 0.99 <= total_prob <= 1.01
        passed = len(scenarios) >= 3 and prob_ok
        details: list[str] = []
        if not prob_ok:
            if total_prob == 0:
                details.append("所有情景概率均为 0，请为 optimistic / base_case / pessimistic 分配有效概率")
            else:
                details.append(f"情景概率之和为 {total_prob:.2f}，建议归一化到 1.0")

        self.results.append(
            CheckResult(
                "scenario_analysis",
                passed,
                f"情景分析包含 {len(scenarios)} 个情景"
                if passed
                else f"情景分析不完整: {details}",
                details,
            )
        )

    def check_risks(self) -> None:
        has_risks = bool(self.snapshot.risks) or bool(self.snapshot.risks_typed)
        self.results.append(
            CheckResult(
                "risks",
                has_risks,
                "风险列表非空" if has_risks else "缺少风险列表（Section XI）",
                [] if has_risks else ["必须提供 risks 或 risks_typed"],
            )
        )

    def check_industry_supply_chain(self) -> None:
        isc = self.snapshot.industry_supply_chain
        passed = isc is not None and bool(isc.industry_overview)
        self.results.append(
            CheckResult(
                "industry_supply_chain",
                passed,
                "行业与产业链模块存在" if passed else "缺少 industry_supply_chain（Section XII）",
                [] if passed else ["必须包含行业概述与产业链 supply_chain"],
            )
        )

    def check_stock_price_data(self) -> None:
        spd = self.snapshot.stock_price_data
        passed = spd is not None and spd.current_price > 0
        self.results.append(
            CheckResult(
                "stock_price_data",
                passed,
                "股价与交易数据模块存在" if passed else "缺少 stock_price_data（Section XIII）",
                [] if passed else ["必须包含 current_price、52w 高低、市值、估值倍数等"],
            )
        )


def validate_snapshot_file(path: Path) -> dict[str, Any]:
    """读取 snapshot.json 并返回校验结果字典。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    snapshot = ResearchSnapshot.model_validate(data)
    validator = SnapshotValidator(snapshot)
    validator.run_all()
    return validator.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="ResearchSnapshot 结构校验")
    parser.add_argument("snapshot_path", type=Path, help="snapshot.json 路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    result = validate_snapshot_file(args.snapshot_path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"校验通过: {result['checks_passed']}")
        if result["issues"]:
            print("问题:")
            for issue in result["issues"]:
                print(f"  - {issue}")

    return 0 if result["checks_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
