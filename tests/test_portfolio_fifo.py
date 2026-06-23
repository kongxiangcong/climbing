"""FIFO 持仓推导测试。"""

from datetime import date
from decimal import Decimal

import pytest

from src.analysis.portfolio_returns import derive_position_lots
from src.common.models import Transaction


def _tx(
    ticker: str,
    side: str,
    quantity: int,
    price: str,
    fee: str = "0",
    trade_date: str = "2026-06-20",
) -> Transaction:
    return Transaction(
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        fee=Decimal(fee),
        trade_date=date.fromisoformat(trade_date),
    )


def test_fifo_buy_only_aggregates_lots() -> None:
    transactions = [
        _tx("000725.SZ", "buy", 100, "5.20", "5"),
        _tx("000725.SZ", "buy", 200, "5.30", "10"),
    ]
    positions, realized = derive_position_lots(transactions)
    assert realized == Decimal("0")
    assert len(positions) == 2

    lot1, lot2 = positions
    assert lot1.quantity == 100
    assert lot1.cost_basis == Decimal("5.25")  # (520 + 5) / 100
    assert lot2.quantity == 200
    assert lot2.cost_basis == Decimal("5.35")  # (1060 + 10) / 200


def test_fifo_partial_sell_matches_oldest_lot() -> None:
    transactions = [
        _tx("000725.SZ", "buy", 100, "5.00", "0"),
        _tx("000725.SZ", "buy", 100, "6.00", "0"),
        _tx("000725.SZ", "sell", 50, "5.50", "5"),
    ]
    market_prices = {"000725.SZ": Decimal("6.50")}
    positions, realized = derive_position_lots(transactions, market_prices)

    # 卖出 50 股来自第一笔 lot，实现盈亏 = 50*5.50 - 5 - 50*5.00 = 20
    assert realized == Decimal("20")
    assert len(positions) == 2
    assert positions[0].quantity == 50
    assert positions[0].realized_pnl == Decimal("20")
    assert positions[0].market_price == Decimal("6.50")
    assert positions[0].unrealized_pnl == Decimal("75")  # 50 * (6.50 - 5.00)

    assert positions[1].quantity == 100
    assert positions[1].cost_basis == Decimal("6.00")


def test_fifo_full_sell_removes_position() -> None:
    transactions = [
        _tx("000725.SZ", "buy", 100, "5.00", "10"),
        _tx("000725.SZ", "sell", 100, "6.00", "10"),
    ]
    positions, realized = derive_position_lots(transactions)
    assert len(positions) == 0
    # cost_basis per share = (500 + 10)/100 = 5.10
    # realized = 600 - 10 - 510 = 80
    assert realized == Decimal("80")


def test_fifo_sell_more_than_position_raises() -> None:
    transactions = [
        _tx("000725.SZ", "buy", 100, "5.00"),
        _tx("000725.SZ", "sell", 150, "6.00"),
    ]
    with pytest.raises(Exception):
        derive_position_lots(transactions)


def test_fifo_pnl_identity_with_sell() -> None:
    """已实现 + 浮动盈亏 = 剩余市值 + 累计净现金流。"""
    transactions = [
        _tx("000725.SZ", "buy", 100, "5.00", "10", "2026-06-18"),
        _tx("000725.SZ", "buy", 100, "6.00", "10", "2026-06-19"),
        _tx("000725.SZ", "sell", 80, "7.00", "16", "2026-06-20"),
    ]
    current_price = Decimal("8.00")
    positions, realized = derive_position_lots(transactions, {"000725.SZ": current_price})

    remaining_qty = sum(p.quantity for p in positions)
    remaining_market_value = sum(p.market_value or Decimal("0") for p in positions)
    total_unrealized = sum(p.unrealized_pnl or Decimal("0") for p in positions)

    # 累计净现金流（流出为负）
    net_cash_flow = Decimal("0")
    for tx in transactions:
        if tx.side == "buy":
            net_cash_flow -= tx.price * Decimal(tx.quantity) + tx.fee
        else:
            net_cash_flow += tx.price * Decimal(tx.quantity) - tx.fee

    assert remaining_qty == 120
    assert realized + total_unrealized == remaining_market_value + net_cash_flow
