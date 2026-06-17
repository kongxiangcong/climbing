"""Pydantic 共享数据模型。"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceMetadata(BaseModel):
    """数据来源元数据。"""

    source: str
    retrieved_at: datetime
    version: str = "1.0.0"
    url: str | None = None
    notes: str | None = None


class Security(BaseModel):
    """证券主数据。"""

    ticker: str
    name: str
    market: str
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

    DRAFT = "草稿"
    ACTIVE = "激活"
    PARTIALLY_TRIGGERED = "部分触发"
    FULLY_TRIGGERED = "完全触发"
    ASSUMPTION_BROKEN = "假设被破坏"
    CLOSED = "关闭"
    REVIEWED = "复盘完成"


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
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: str | None = None


class Snapshot(BaseModel):
    """报告快照。"""

    snapshot_id: str
    report_type: str
    ticker: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    version: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
