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


class Valuation(BaseModel):
    """估值区间。"""

    method: str
    value_low: Decimal | None = None
    value_high: Decimal | None = None
    assumptions: list[str] = Field(default_factory=list)


class ResearchSnapshot(Snapshot):
    """个股深度研报快照。"""

    report_type: Literal["research"] = "research"
    ticker: str
    summary: str = ""
    six_dimensions: dict[str, Any] = Field(default_factory=dict)
    valuation: Valuation = Field(default_factory=lambda: Valuation(method="unknown"))
    risks: list[str] = Field(default_factory=list)
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
