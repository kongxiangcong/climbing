"""将 equity-researcher 输出 schema 映射为 Climbing ResearchSnapshot。"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from src.common.models import (
    BusinessSegment,
    CatalystEvent,
    CapitalMarketStructure,
    CompanyOverview,
    ComparableCompany,
    ConsensusExpectations,
    CoreNarrative,
    DCF,
    DimensionAnalysis,
    Factor,
    FinancialData,
    HistoricalBand,
    IndustrySupplyChain,
    InvestmentLogic,
    InvestmentLogicPeriod,
    InvestmentThesisRow,
    ResearchMetadata,
    ResearchSnapshot,
    RiskItem,
    Scenario,
    SourceMetadata,
    StockPriceData,
    SupplyChainNode,
    Valuation,
    ValuationData,
)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _build_source_metadata(source: str = "skills/stock-research") -> SourceMetadata:
    return SourceMetadata(
        source=source,
        retrieved_at=datetime.now(),
        version="1.0.0",
    )


def build_research_snapshot_from_skill_output(
    ticker: str,
    version: str,
    skill_output: dict[str, Any],
    source: str = "skills/stock-research",
) -> ResearchSnapshot:
    """将 equity-researcher 13-section 输出转换为 ResearchSnapshot。

    同时兼容旧版 fixture（仅含 summary / six_dimensions dict 等字段）。
    """
    metadata = skill_output.get("metadata", {})
    core_narrative = skill_output.get("core_narrative", {})

    # Section I: Metadata
    research_metadata = None
    if metadata:
        research_metadata = ResearchMetadata(
            company_name=metadata.get("company_name", ""),
            ticker=metadata.get("ticker", ticker),
            market=metadata.get("market", "A-share"),
            report_language=metadata.get("report_language", "zh-CN"),
            report_date=metadata.get("report_date"),
            latest_trading_date=metadata.get("latest_trading_date"),
            latest_financial_report=metadata.get("latest_financial_report", ""),
            next_earnings_date=metadata.get("next_earnings_date"),
            benchmark_index=metadata.get("benchmark_index", ""),
            benchmark_name=metadata.get("benchmark_name", ""),
            output_level=metadata.get("output_level", "equity-report"),
        )

    # Section II: Core Narrative
    core_narrative_obj = None
    if core_narrative:
        core_narrative_obj = CoreNarrative(
            core_narrative=core_narrative.get("core_narrative", ""),
            main_title=core_narrative.get("main_title", ""),
            sub_title=core_narrative.get("sub_title", ""),
            core_viewpoint=core_narrative.get("core_viewpoint", ""),
        )

    # Section III: Six-Dimension Analysis
    six_dimensions_raw = skill_output.get("six_dimensions", {})
    six_dimensions_typed: list[DimensionAnalysis] = []
    six_dimensions_dict: dict[str, Any] = {}
    if isinstance(six_dimensions_raw, list):
        for item in six_dimensions_raw:
            dim = DimensionAnalysis(
                dimension_id=item.get("dimension_id", "H1"),
                dimension_name=item.get("dimension_name", ""),
                conclusion=item.get("conclusion", ""),
                key_data_support=item.get("key_data_support", []),
                so_what=item.get("so_what", ""),
                anomalies=item.get("anomalies"),
                information_class=item.get("information_class"),
            )
            six_dimensions_typed.append(dim)
            six_dimensions_dict[dim.dimension_id] = dim.conclusion
    elif isinstance(six_dimensions_raw, dict):
        six_dimensions_dict = dict(six_dimensions_raw)

    # Section IV: Investment Logic
    investment_logic_raw = skill_output.get("investment_logic", {})
    investment_logic = None
    if investment_logic_raw:

        def _period(raw: dict[str, Any]) -> InvestmentLogicPeriod:
            return InvestmentLogicPeriod(
                bull_factors=[
                    Factor(
                        description=f.get("description", ""),
                        data_support=f.get("data_support", ""),
                        inflection_condition=f.get("inflection_condition"),
                        pricing_level=f.get("pricing_level"),
                        risk_level=f.get("risk_level"),
                        trigger_condition=f.get("trigger_condition"),
                    )
                    for f in raw.get("bull_factors", [])
                ],
                bear_factors=[
                    Factor(
                        description=f.get("description", ""),
                        data_support=f.get("data_support", ""),
                        inflection_condition=f.get("inflection_condition"),
                        pricing_level=f.get("pricing_level"),
                        risk_level=f.get("risk_level"),
                        trigger_condition=f.get("trigger_condition"),
                    )
                    for f in raw.get("bear_factors", [])
                ],
                capital_market_structure=(
                    CapitalMarketStructure(
                        description=raw["capital_market_structure"].get("description", ""),
                        data_support=raw["capital_market_structure"].get("data_support", ""),
                    )
                    if raw.get("capital_market_structure")
                    else None
                ),
            )

        investment_logic = InvestmentLogic(
            short_term=_period(investment_logic_raw.get("short_term", {})),
            long_term=_period(investment_logic_raw.get("long_term", {})),
        )

    # Section V: Investment Thesis Table
    investment_thesis_table = [
        InvestmentThesisRow(
            dimension=row.get("dimension", ""),
            bull_arguments=row.get("bull_arguments", ""),
            bear_arguments=row.get("bear_arguments", ""),
            key_assumption=row.get("key_assumption", ""),
            turning_point_signal=row.get("turning_point_signal", ""),
            judgment=row.get("judgment", ""),
        )
        for row in skill_output.get("investment_thesis_table", [])
    ]

    # Section VI: Company Overview
    company_overview_raw = skill_output.get("company_overview", {})
    company_overview = None
    if company_overview_raw:
        company_overview = CompanyOverview(
            background=company_overview_raw.get("background", {}),
            business_model=company_overview_raw.get("business_model", {}),
            recent_developments=company_overview_raw.get("recent_developments", {}),
            business_segments=[
                BusinessSegment(
                    segment_name=seg.get("segment_name", ""),
                    revenue=seg.get("revenue", 0.0),
                    revenue_pct=seg.get("revenue_pct", 0.0),
                    yoy_growth=seg.get("yoy_growth", 0.0),
                    gross_margin=seg.get("gross_margin", 0.0),
                )
                for seg in company_overview_raw.get("business_segments", [])
            ],
        )

    # Section VII: Financial Data
    financial_data_raw = skill_output.get("financial_data", {})
    financial_data = None
    if financial_data_raw:
        financial_data = FinancialData(
            income_statement=financial_data_raw.get("income_statement", {}),
            balance_sheet_highlights=financial_data_raw.get("balance_sheet_highlights", {}),
            cash_flow_highlights=financial_data_raw.get("cash_flow_highlights", {}),
            earnings_quality_signals=financial_data_raw.get("earnings_quality_signals", []),
            key_ratios=financial_data_raw.get("key_ratios", {}),
        )

    # Section VIII: Valuation Data
    valuation_raw = skill_output.get("valuation", {})
    valuation = Valuation(
        method=valuation_raw.get("method", "unknown") if valuation_raw else "unknown",
        value_low=_to_decimal(valuation_raw.get("value_low")) if valuation_raw else None,
        value_high=_to_decimal(valuation_raw.get("value_high")) if valuation_raw else None,
        assumptions=valuation_raw.get("assumptions", []) if valuation_raw else [],
    )

    valuation_data = None
    valuation_data_raw = skill_output.get("valuation_data", {})
    if valuation_data_raw:
        dcf_raw = valuation_data_raw.get("dcf")
        dcf = None
        if dcf_raw:
            dcf = DCF(
                wacc=dcf_raw.get("wacc", 0.0),
                terminal_growth=dcf_raw.get("terminal_growth", 0.0),
                fcf_projections=dcf_raw.get("fcf_projections", []),
                terminal_value=dcf_raw.get("terminal_value", 0.0),
                enterprise_value=dcf_raw.get("enterprise_value", 0.0),
                equity_value_per_share=dcf_raw.get("equity_value_per_share", 0.0),
                sensitivity_matrix=dcf_raw.get("sensitivity_matrix", {}),
            )

        historical_band_raw = valuation_data_raw.get("historical_band")
        historical_band = None
        if historical_band_raw:
            historical_band = HistoricalBand(
                pe_band=historical_band_raw.get("pe_band", {}),
                pb_band=historical_band_raw.get("pb_band", {}),
            )

        consensus_raw = valuation_data_raw.get("consensus_expectations")
        consensus = None
        if consensus_raw:
            consensus = ConsensusExpectations(
                coverage_count=consensus_raw.get("coverage_count", 0),
                eps_forecast=consensus_raw.get("eps_forecast", 0.0),
                revenue_forecast=consensus_raw.get("revenue_forecast", 0.0),
                revision_trend=consensus_raw.get("revision_trend", ""),
                peg=consensus_raw.get("peg"),
            )

        valuation_data = ValuationData(
            valuation_table=valuation_data_raw.get("valuation_table", {}),
            consensus_expectations=consensus,
            comparable_companies=[
                ComparableCompany(
                    name=c.get("name", ""),
                    ticker=c.get("ticker", ""),
                    market_cap=c.get("market_cap", 0.0),
                    pe=c.get("pe"),
                    pb=c.get("pb"),
                    ps=c.get("ps"),
                    ev_ebitda=c.get("ev_ebitda"),
                )
                for c in valuation_data_raw.get("comparable_companies", [])
            ],
            industry_average=valuation_data_raw.get("industry_average", {}),
            premium_discount_analysis=valuation_data_raw.get("premium_discount_analysis", ""),
            dcf=dcf,
            historical_band=historical_band,
            sotp=valuation_data_raw.get("sotp"),
            valuation_synthesis=valuation_data_raw.get("valuation_synthesis"),
        )

    # Section IX: Catalyst Calendar
    catalyst_calendar = [
        CatalystEvent(
            event_date=c.get("event_date") or c.get("date"),
            event=c.get("event", ""),
            importance=c.get("importance", "Medium"),
            impact_analysis=c.get("impact_analysis", ""),
            market_expectation=c.get("market_expectation", ""),
            source=c.get("source", ""),
        )
        for c in skill_output.get("catalyst_calendar", [])
    ]

    # Section X: Scenario Analysis
    scenario_analysis = {
        name: Scenario(
            probability=s.get("probability", 0.0),
            assumptions=s.get("assumptions", ""),
            revenue=s.get("revenue", 0.0),
            net_income=s.get("net_income", 0.0),
            target_pe=s.get("target_pe", 0.0),
            implied_market_cap=s.get("implied_market_cap", 0.0),
        )
        for name, s in skill_output.get("scenario_analysis", {}).items()
    }

    # Section XI: Risk List
    risks = skill_output.get("risks", [])
    risks_typed = [
        RiskItem(
            risk_type=r.get("risk_type", ""),
            description=r.get("description", ""),
            impact=r.get("impact", "Medium"),
            probability=r.get("probability", "Medium"),
            monitoring_signal=r.get("monitoring_signal"),
        )
        for r in skill_output.get("risks_typed", [])
    ]

    # Section XII: Industry & Supply Chain
    industry_supply_chain = None
    isc_raw = skill_output.get("industry_supply_chain", {})
    if isc_raw:
        supply_chain_raw = isc_raw.get("supply_chain", {})
        supply_chain = {
            key: [SupplyChainNode(name=n.get("name", ""), role=n.get("role", "")) for n in nodes]
            for key, nodes in supply_chain_raw.items()
        }
        industry_supply_chain = IndustrySupplyChain(
            industry_overview=isc_raw.get("industry_overview", ""),
            market_concentration=isc_raw.get("market_concentration", ""),
            pricing_power=isc_raw.get("pricing_power", ""),
            entry_barriers=isc_raw.get("entry_barriers", ""),
            competitive_trend=isc_raw.get("competitive_trend", ""),
            supply_chain=supply_chain,
        )

    # Section XIII: Stock Price & Trading Data
    stock_price_data = None
    spd_raw = skill_output.get("stock_price_data", {})
    if spd_raw:
        stock_price_data = StockPriceData(
            stock_csv_path=spd_raw.get("stock_csv_path"),
            benchmark_csv_path=spd_raw.get("benchmark_csv_path"),
            current_price=spd_raw.get("current_price", 0.0),
            high_52w=spd_raw.get("high_52w") or spd_raw.get("52w_high") or 0.0,
            low_52w=spd_raw.get("low_52w") or spd_raw.get("52w_low") or 0.0,
            market_cap=spd_raw.get("market_cap", 0.0),
            pe_ttm=spd_raw.get("pe_ttm", 0.0),
            pb=spd_raw.get("pb", 0.0),
            daily_volume=spd_raw.get("daily_volume", 0.0),
            turnover_rate=spd_raw.get("turnover_rate", 0.0),
            beta=spd_raw.get("beta", 0.0),
            dividend_yield=spd_raw.get("dividend_yield", 0.0),
        )

    summary = skill_output.get("summary", "")
    if not summary and core_narrative_obj:
        summary = core_narrative_obj.core_viewpoint or core_narrative_obj.core_narrative

    return ResearchSnapshot(
        snapshot_id=f"research-{ticker}-{version}",
        version=version,
        ticker=ticker,
        summary=summary,
        six_dimensions=six_dimensions_dict,
        six_dimensions_typed=six_dimensions_typed,
        research_metadata=research_metadata,
        core_narrative=core_narrative_obj,
        investment_logic=investment_logic,
        investment_thesis_table=investment_thesis_table,
        company_overview=company_overview,
        financial_data=financial_data,
        valuation=valuation,
        valuation_data=valuation_data,
        catalyst_calendar=catalyst_calendar,
        scenario_analysis=scenario_analysis,
        risks=risks,
        risks_typed=risks_typed,
        assumptions=skill_output.get("assumptions", []),
        invalidation_conditions=skill_output.get("invalidation_conditions", []),
        target_price_low=_to_decimal(skill_output.get("target_price_low")),
        target_price_high=_to_decimal(skill_output.get("target_price_high")),
        industry_supply_chain=industry_supply_chain,
        stock_price_data=stock_price_data,
        pdf_path=skill_output.get("pdf_path"),
        references=skill_output.get("references", []),
        metadata=_build_source_metadata(source),
    )
