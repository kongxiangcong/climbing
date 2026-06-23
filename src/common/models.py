"""Pydantic 共享数据模型。"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceMetadata(BaseModel):
    """数据来源元数据。"""

    source: str
    retrieved_at: datetime
    version: str = "1.0.0"
    tier: int | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    url: str | None = None
    notes: str | None = None


class Security(BaseModel):
    """证券主数据。"""

    ticker: str
    name: str
    market: str
    asset_class: str | None = None
    sector: str | None = None
    industry: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: SourceMetadata | None = None


class PriceBar(BaseModel):
    """价格 OHLCV。"""

    ticker: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal | None = None
    metadata: SourceMetadata | None = None


class TransactionSide(str, Enum):
    """交易方向。"""

    BUY = "buy"
    SELL = "sell"


class Transaction(BaseModel):
    """标准化交易流水记录。"""

    ticker: str
    side: str  # buy / sell
    quantity: int = Field(ge=1)
    price: Decimal = Field(ge=Decimal("0"))
    fee: Decimal = Decimal("0")
    trade_date: date
    account: str = "default"
    name: str | None = None
    notes: str | None = None
    raw_source: str | None = None
    metadata: SourceMetadata | None = None


class Position(BaseModel):
    """持仓记录。"""

    ticker: str
    buy_date: date
    buy_price: Decimal
    quantity: int
    fee: Decimal = Decimal("0")
    account: str = "default"
    notes: str | None = None


class TradePlanStatus(str, Enum):
    """交易计划状态。"""

    DRAFT = "draft"
    ACTIVE = "active"
    PARTIALLY_TRIGGERED = "partially_triggered"
    FULLY_TRIGGERED = "fully_triggered"
    ASSUMPTION_BROKEN = "assumption_broken"
    CLOSED = "closed"
    REVIEWED = "reviewed"


class TradePlan(BaseModel):
    """交易计划对象。"""

    plan_id: str
    name: str
    ticker: str
    direction: str  # long / short
    time_window: str
    research_version: str
    entry_logic: str
    target_price_low: Decimal | None = None
    target_price_high: Decimal | None = None
    position_limit: Decimal = Decimal("10")  # 仓位上限 %
    risk_budget: Decimal = Decimal("2")  # 风险预算 %
    invalidation_conditions: list[str] = Field(default_factory=list)
    alternative_scenarios: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    review_frequency: str = "weekly"
    status: TradePlanStatus = TradePlanStatus.DRAFT
    plan_version: str = "1"
    source_snapshots: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: str | None = None
    metadata: SourceMetadata | None = None


# ---------------------------------------------------------------------------
# Snapshot schema
# ---------------------------------------------------------------------------


class Snapshot(BaseModel):
    """快照基类。所有 snapshot 必须以结构化 JSON 落盘，包含可追溯元数据。"""

    model_config = ConfigDict(extra="allow")

    snapshot_id: str
    report_type: str
    created_at: datetime = Field(default_factory=datetime.now)
    version: str
    data_cutoff: date | datetime | None = None
    metadata: SourceMetadata


class IndexMetric(BaseModel):
    """指数/市场指标。"""

    ticker: str
    name: str
    close: Decimal
    change_pct: Decimal
    volume: int | None = None


class SectorHeat(BaseModel):
    """板块热度。"""

    name: str
    score: float
    change_pct: Decimal | None = None


class MarketSnapshot(Snapshot):
    """市场事实快照。"""

    report_type: Literal["market"] = "market"
    trade_date: date
    indices: list[IndexMetric] = Field(default_factory=list)
    breadth: dict[str, int] = Field(default_factory=dict)
    total_turnover: Decimal | None = None
    sector_heat: list[SectorHeat] = Field(default_factory=list)
    margin_balance: Decimal | None = None
    northbound_flow: Decimal | None = None
    etf_flow: dict[str, Decimal] = Field(default_factory=dict)
    sentiment_score: float | None = None
    risk_appetite: str | None = None


class PositionLot(BaseModel):
    """持仓明细（由交易流水 FIFO 推导）。"""

    ticker: str
    quantity: int
    cost_basis: Decimal
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal = Decimal("0")
    account: str = "default"


class Exposure(BaseModel):
    """组合暴露。"""

    category: str
    value_pct: Decimal


class PortfolioSnapshot(Snapshot):
    """账户事实快照。"""

    report_type: Literal["portfolio"] = "portfolio"
    account: str = "default"
    trade_date: date = Field(default_factory=date.today)
    cash: Decimal = Decimal("0")
    total_assets: Decimal = Decimal("0")
    total_market_value: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    positions: list[PositionLot] = Field(default_factory=list)
    sector_exposure: list[Exposure] = Field(default_factory=list)
    max_drawdown: Decimal | None = None
    volatility: Decimal | None = None
    modified_dietz_return: Decimal | None = None
    twrr: Decimal | None = None
    plan_linkages: dict[str, list[str]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 个股研报（equity-researcher）结构化子模型
# ---------------------------------------------------------------------------


class Valuation(BaseModel):
    """估值区间。"""

    method: str
    value_low: Decimal | None = None
    value_high: Decimal | None = None
    assumptions: list[str] = Field(default_factory=list)


class ResearchMetadata(BaseModel):
    """个股研报元数据（对应 equity-researcher Section I）。"""

    company_name: str = ""
    ticker: str = ""
    market: Literal["A-share", "HK", "US"] = "A-share"
    report_language: Literal["zh-CN", "en"] = "zh-CN"
    report_date: date = Field(default_factory=date.today)
    latest_trading_date: date = Field(default_factory=date.today)
    latest_financial_report: str = ""
    next_earnings_date: date | None = None
    benchmark_index: str = ""
    benchmark_name: str = ""
    output_level: Literal["tear-sheet", "equity-report"] = "equity-report"


class CoreNarrative(BaseModel):
    """核心投资叙事（对应 equity-researcher Section II）。"""

    core_narrative: str = ""
    main_title: str = ""
    sub_title: str = ""
    core_viewpoint: str = ""


class DimensionAnalysis(BaseModel):
    """六维分析单维度结构（对应 equity-researcher Section III）。"""

    dimension_id: Literal["H1", "H2", "H3", "H4", "H5", "H6"]
    dimension_name: str = ""
    conclusion: str = ""
    key_data_support: list[str] = Field(default_factory=list)
    so_what: str = ""
    anomalies: list[str] | None = None
    information_class: Literal["verified", "partially_verified", "unverified"] | None = None


class Factor(BaseModel):
    """投资逻辑多空因子。"""

    description: str = ""
    data_support: str = ""
    inflection_condition: str | None = None
    pricing_level: str | None = None
    risk_level: Literal["High", "Medium", "Low"] | None = None
    trigger_condition: str | None = None


class CapitalMarketStructure(BaseModel):
    """资本市场结构分析。"""

    description: str = ""
    data_support: str = ""


class InvestmentLogicPeriod(BaseModel):
    """短期或长期投资逻辑。"""

    bull_factors: list[Factor] = Field(default_factory=list)
    bear_factors: list[Factor] = Field(default_factory=list)
    capital_market_structure: CapitalMarketStructure | None = None


class InvestmentLogic(BaseModel):
    """投资逻辑（对应 equity-researcher Section IV）。"""

    short_term: InvestmentLogicPeriod = Field(default_factory=InvestmentLogicPeriod)
    long_term: InvestmentLogicPeriod = Field(default_factory=InvestmentLogicPeriod)


class InvestmentThesisRow(BaseModel):
    """投资论点综合分析表行（对应 equity-researcher Section V）。"""

    dimension: str = ""
    bull_arguments: str = ""
    bear_arguments: str = ""
    key_assumption: str = ""
    turning_point_signal: str = ""
    judgment: str = ""


class BusinessSegment(BaseModel):
    """公司业务分部。"""

    segment_name: str = ""
    revenue: float = 0.0
    revenue_pct: float = 0.0
    yoy_growth: float = 0.0
    gross_margin: float = 0.0


class CompanyOverview(BaseModel):
    """公司概览（对应 equity-researcher Section VI）。"""

    background: dict[str, str] = Field(default_factory=dict)
    business_model: dict[str, str] = Field(default_factory=dict)
    recent_developments: dict[str, str] = Field(default_factory=dict)
    business_segments: list[BusinessSegment] = Field(default_factory=list)


class FinancialData(BaseModel):
    """财务数据（对应 equity-researcher Section VII）。"""

    income_statement: dict[str, Any] = Field(default_factory=dict)
    balance_sheet_highlights: dict[str, Any] = Field(default_factory=dict)
    cash_flow_highlights: dict[str, Any] = Field(default_factory=dict)
    earnings_quality_signals: list[str] = Field(default_factory=list)
    key_ratios: dict[str, dict[str, float]] = Field(default_factory=dict)


class ComparableCompany(BaseModel):
    """可比公司。"""

    name: str = ""
    ticker: str = ""
    market_cap: float = 0.0
    pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    ev_ebitda: float | None = None


class ConsensusExpectations(BaseModel):
    """一致预期。"""

    coverage_count: int = 0
    eps_forecast: float = 0.0
    revenue_forecast: float = 0.0
    revision_trend: str = ""
    peg: float | None = None


class DCF(BaseModel):
    """DCF 估值（L2）。"""

    wacc: float = 0.0
    terminal_growth: float = 0.0
    fcf_projections: list[float] = Field(default_factory=list)
    terminal_value: float = 0.0
    enterprise_value: float = 0.0
    equity_value_per_share: float = 0.0
    sensitivity_matrix: dict[str, Any] = Field(default_factory=dict)


class HistoricalBand(BaseModel):
    """历史估值带。"""

    pe_band: dict[str, float] = Field(default_factory=dict)
    pb_band: dict[str, float] = Field(default_factory=dict)


class ValuationData(BaseModel):
    """估值数据（对应 equity-researcher Section VIII）。"""

    valuation_table: dict[str, Any] = Field(default_factory=dict)
    consensus_expectations: ConsensusExpectations | None = None
    comparable_companies: list[ComparableCompany] = Field(default_factory=list)
    industry_average: dict[str, float] = Field(default_factory=dict)
    premium_discount_analysis: str = ""
    dcf: DCF | None = None
    historical_band: HistoricalBand | None = None
    sotp: dict[str, Any] | None = None
    valuation_synthesis: str | None = None


class CatalystEvent(BaseModel):
    """催化剂事件（对应 equity-researcher Section IX）。"""

    event_date: date | None = None
    event: str = ""
    importance: Literal["High", "Medium", "Low"] = "Medium"
    impact_analysis: str = ""
    market_expectation: str = ""
    source: str = ""


class Scenario(BaseModel):
    """情景分析（对应 equity-researcher Section X）。"""

    probability: float = Field(default=0.0, ge=0.0, le=1.0)
    assumptions: str = ""
    revenue: float = 0.0
    net_income: float = 0.0
    target_pe: float = 0.0
    implied_market_cap: float = 0.0


class RiskItem(BaseModel):
    """结构化风险项（对应 equity-researcher Section XI）。"""

    risk_type: str = ""
    description: str = ""
    impact: Literal["High", "Medium", "Low"] = "Medium"
    probability: Literal["High", "Medium", "Low"] = "Medium"
    monitoring_signal: str | None = None


class SupplyChainNode(BaseModel):
    """产业链节点。"""

    name: str = ""
    role: str = ""


class IndustrySupplyChain(BaseModel):
    """行业与产业链（对应 equity-researcher Section XII）。"""

    industry_overview: str = ""
    market_concentration: str = ""
    pricing_power: str = ""
    entry_barriers: str = ""
    competitive_trend: str = ""
    supply_chain: dict[str, list[SupplyChainNode]] = Field(default_factory=dict)


class StockPriceData(BaseModel):
    """股价与交易数据（对应 equity-researcher Section XIII）。"""

    stock_csv_path: str | None = None
    benchmark_csv_path: str | None = None
    current_price: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    market_cap: float = 0.0
    pe_ttm: float = 0.0
    pb: float = 0.0
    daily_volume: float = 0.0
    turnover_rate: float = 0.0
    beta: float = 0.0
    dividend_yield: float = 0.0


class ResearchSnapshot(Snapshot):
    """个股深度研报快照。"""

    report_type: Literal["research"] = "research"
    ticker: str
    summary: str = ""

    # 兼容旧字段：保留原有 loose dict / list[str]
    six_dimensions: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)

    # equity-researcher 13 个 section 的强类型扩展（均为可选，向后兼容）
    research_metadata: ResearchMetadata | None = None
    core_narrative: CoreNarrative | None = None
    six_dimensions_typed: list[DimensionAnalysis] = Field(default_factory=list)
    investment_logic: InvestmentLogic | None = None
    investment_thesis_table: list[InvestmentThesisRow] = Field(default_factory=list)
    company_overview: CompanyOverview | None = None
    financial_data: FinancialData | None = None
    valuation: Valuation = Field(default_factory=lambda: Valuation(method="unknown"))
    valuation_data: ValuationData | None = None
    catalyst_calendar: list[CatalystEvent] = Field(default_factory=list)
    scenario_analysis: dict[str, Scenario] = Field(default_factory=dict)
    risks_typed: list[RiskItem] = Field(default_factory=list)
    industry_supply_chain: IndustrySupplyChain | None = None
    stock_price_data: StockPriceData | None = None

    assumptions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    target_price_low: Decimal | None = None
    target_price_high: Decimal | None = None
    pdf_path: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)


class DeviationAlert(BaseModel):
    """计划偏离告警。"""

    plan_id: str
    reason: str
    severity: str = "moderate"


class ResearchAlert(BaseModel):
    """研究过期/需要重跑提示。"""

    ticker: str
    reason: str


class DailyReviewSnapshot(Snapshot):
    """每日复盘分析快照。"""

    report_type: Literal["daily_review"] = "daily_review"
    trade_date: date
    highlights: list[str] = Field(default_factory=list)
    sentiment: str = ""
    portfolio_risk: dict[str, Any] = Field(default_factory=dict)
    plan_deviations: list[DeviationAlert] = Field(default_factory=list)
    stale_research: list[ResearchAlert] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)


class PlanReviewSnapshot(Snapshot):
    """交易计划复核记录快照。"""

    report_type: Literal["plan_review"] = "plan_review"
    plan_id: str
    plan_version: str = "1"
    triggered_conditions: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    recommendation: str = ""
    user_decision: str | None = None
