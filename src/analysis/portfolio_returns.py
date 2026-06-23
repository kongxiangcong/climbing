"""持仓与收益计算引擎。

- 按 FIFO 从交易流水推导当前持仓（lot）。
- 计算浮动盈亏、已实现收益、仓位比例、行业/板块暴露。
- 提供资金加权收益率（Modified Dietz）和时间加权收益率（TWRR）工具函数。
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from src.common.config import settings
from src.common.models import Exposure, PositionLot, Transaction
from src.data_standardization.price_lookup import load_latest_price


class InsufficientPositionError(ValueError):
    """卖出数量超过当前可卖持仓时抛出。"""


class Lot:
    """内部 lot 对象，用于 FIFO 拆分。"""

    def __init__(self, ticker: str, quantity: int, cost_basis: Decimal, account: str) -> None:
        self.ticker = ticker
        self.quantity = quantity
        self.cost_basis = cost_basis  # 含买入费用的每股成本
        self.account = account
        self.realized_pnl = Decimal("0")


def _allocate_fee(total_fee: Decimal, allocated_qty: int, total_qty: int) -> Decimal:
    """按卖出数量比例分摊卖出费用。"""
    if total_qty == 0:
        return Decimal("0")
    return (total_fee * Decimal(allocated_qty) / Decimal(total_qty)).quantize(
        Decimal("0.0001")
    )


def _derive_ticker_lots(transactions: list[Transaction]) -> tuple[list[Lot], Decimal]:
    """对单只标的按时间顺序 FIFO 推导 lot 与已实现收益。

    返回 ``(open_lots, total_realized_pnl)``。
    """
    open_lots: list[Lot] = []
    total_realized = Decimal("0")

    for tx in transactions:
        if tx.side == "buy":
            if tx.quantity <= 0:
                raise ValueError(f"买入数量必须大于 0：{tx.ticker} {tx.quantity}")
            # 买入费用计入每股成本
            total_cost = tx.price * Decimal(tx.quantity) + tx.fee
            cost_per_share = total_cost / Decimal(tx.quantity)
            open_lots.append(
                Lot(
                    ticker=tx.ticker,
                    quantity=tx.quantity,
                    cost_basis=cost_per_share,
                    account=tx.account,
                )
            )
        elif tx.side == "sell":
            if tx.quantity <= 0:
                raise ValueError(f"卖出数量必须大于 0：{tx.ticker} {tx.quantity}")
            remaining = tx.quantity
            while remaining > 0:
                if not open_lots:
                    raise InsufficientPositionError(
                        f"{tx.ticker} 卖出 {tx.quantity} 股，但当前无可用持仓"
                    )
                oldest = open_lots[0]
                sell_from_lot = min(remaining, oldest.quantity)
                allocated_fee = _allocate_fee(tx.fee, sell_from_lot, tx.quantity)
                proceeds = tx.price * Decimal(sell_from_lot) - allocated_fee
                realized = proceeds - oldest.cost_basis * Decimal(sell_from_lot)
                oldest.realized_pnl += realized
                total_realized += realized
                oldest.quantity -= sell_from_lot
                remaining -= sell_from_lot
                if oldest.quantity == 0:
                    open_lots.pop(0)

    return open_lots, total_realized


def derive_position_lots(
    transactions: list[Transaction],
    market_prices: dict[str, Decimal] | None = None,
) -> tuple[list[PositionLot], Decimal]:
    """从交易流水推导当前持仓 lot 及总已实现收益。

    ``market_prices`` 为 ``{ticker: price}`` 映射；缺失时使用成本价作为回退。
    """
    by_ticker: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_ticker[tx.ticker].append(tx)

    prices = market_prices or {}
    position_lots: list[PositionLot] = []
    total_realized = Decimal("0")

    for ticker, txs in by_ticker.items():
        txs.sort(key=lambda t: (t.trade_date, t.ticker))
        lots, realized = _derive_ticker_lots(txs)
        total_realized += realized
        market_price = prices[ticker] if ticker in prices else load_latest_price(ticker)

        for lot in lots:
            price = market_price if market_price is not None else lot.cost_basis
            market_value = price * Decimal(lot.quantity)
            unrealized = market_value - lot.cost_basis * Decimal(lot.quantity)
            position_lots.append(
                PositionLot(
                    ticker=lot.ticker,
                    quantity=lot.quantity,
                    cost_basis=lot.cost_basis,
                    market_price=price,
                    market_value=market_value,
                    unrealized_pnl=unrealized,
                    realized_pnl=lot.realized_pnl,
                    account=lot.account,
                )
            )

    return position_lots, total_realized


def _load_sector_map() -> dict[str, str]:
    """从证券主数据表加载 ticker -> sector 映射。"""
    master_path = settings.project_root / "data" / "standardized" / "security_master.json"
    if not master_path.exists():
        return {}
    try:
        data = json.loads(master_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return {}
        return {
            str(item.get("ticker")): str(item.get("sector"))
            for item in data
            if item.get("ticker") and item.get("sector")
        }
    except Exception:
        return {}


def calculate_sector_exposure(positions: list[PositionLot]) -> list[Exposure]:
    """根据持仓市值计算行业暴露。"""
    total_value = sum((p.market_value or Decimal("0")) for p in positions)
    if total_value == 0:
        return []

    sector_map = _load_sector_map()
    by_sector: dict[str, Decimal] = defaultdict(Decimal)
    for p in positions:
        value = p.market_value or Decimal("0")
        sector = sector_map.get(p.ticker, "unknown")
        by_sector[sector] += value

    return sorted(
        [
            Exposure(
                category=sector,
                value_pct=(value / total_value * 100).quantize(Decimal("0.01")),
            )
            for sector, value in by_sector.items()
        ],
        key=lambda e: e.value_pct,
        reverse=True,
    )


def modified_dietz_return(
    begin_value: Decimal,
    end_value: Decimal,
    cash_flows: list[tuple[date | datetime, Decimal]],
    begin_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
) -> Decimal | None:
    """计算资金加权收益率（Modified Dietz）。

    ``cash_flows`` 为元组 ``(flow_date, amount)``，流出为负，流入为正。
    当未提供起止日期或现金流发生在期中时，按 0.5 权重近似。
    """
    total_cf = sum(cf[1] for cf in cash_flows)
    if begin_value == 0 and end_value == 0 and total_cf == 0:
        return None

    weighted_cf = Decimal("0")
    if cash_flows and begin_date is not None and end_date is not None:
        begin = begin_date
        end = end_date
        if isinstance(begin, date):
            begin = datetime.combine(begin, datetime.min.time())
        if isinstance(end, date):
            end = datetime.combine(end, datetime.min.time())
        total_days = (end - begin).days
        if total_days <= 0:
            # 同一天或异常，按期中权重
            weighted_cf = total_cf / Decimal("2")
        else:
            for flow_date, amount in cash_flows:
                fd = flow_date
                if isinstance(fd, date):
                    fd = datetime.combine(fd, datetime.min.time())
                remaining_days = max(0, (end - fd).days)
                weight = Decimal(remaining_days) / Decimal(total_days)
                weighted_cf += amount * weight
    else:
        weighted_cf = total_cf / Decimal("2")

    denominator = begin_value + weighted_cf
    if denominator == 0:
        return None
    return ((end_value - begin_value - total_cf) / denominator).quantize(
        Decimal("0.0001")
    )


def time_weighted_return(
    valuations: list[tuple[date | datetime, Decimal]],
    cash_flows: list[tuple[date | datetime, Decimal]],
) -> Decimal | None:
    """计算时间加权收益率（TWRR）。

    ``valuations`` 为按时间排序的 ``(date, value)`` 组合价值序列；
    ``cash_flows`` 为同期的外部现金流。假设现金流发生在每期期末。
    """
    if len(valuations) < 2:
        return None

    sorted_vals = sorted(valuations, key=lambda x: x[0])
    cf_by_date: dict[str, Decimal] = defaultdict(Decimal)
    for d, amount in cash_flows:
        key = d.isoformat() if isinstance(d, (date, datetime)) else str(d)
        cf_by_date[key] += amount

    product = Decimal("1")
    for i in range(1, len(sorted_vals)):
        prev_date, prev_value = sorted_vals[i - 1]
        curr_date, curr_value = sorted_vals[i]
        cf_key = curr_date.isoformat() if isinstance(curr_date, (date, datetime)) else str(curr_date)
        cf = cf_by_date.get(cf_key, Decimal("0"))
        if prev_value == 0:
            hpr = Decimal("1") if curr_value - cf == 0 else None
            if hpr is None:
                return None
        else:
            hpr = (curr_value - cf) / prev_value
        product *= hpr

    return (product - Decimal("1")).quantize(Decimal("0.0001"))


def calculate_drawdown(values: list[Decimal]) -> Decimal | None:
    """从净值序列计算当前最大回撤。"""
    if not values:
        return None
    peak = Decimal("0")
    max_dd = Decimal("0")
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else Decimal("0")
        if dd > max_dd:
            max_dd = dd
    return max_dd.quantize(Decimal("0.0001"))


def portfolio_summary(
    positions: list[PositionLot],
    realized_pnl: Decimal,
    cash: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """聚合持仓 lot，生成投资组合摘要字典。"""
    total_market_value = sum((p.market_value or Decimal("0")) for p in positions)
    total_unrealized = sum((p.unrealized_pnl or Decimal("0")) for p in positions)
    total_assets = cash + total_market_value

    sector_exposure = calculate_sector_exposure(positions)

    return {
        "cash": cash,
        "total_market_value": total_market_value,
        "total_assets": total_assets,
        "unrealized_pnl": total_unrealized,
        "realized_pnl": realized_pnl,
        "positions": positions,
        "sector_exposure": sector_exposure,
    }
