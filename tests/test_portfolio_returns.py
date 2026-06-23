"""组合收益与风险指标测试。"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.analysis.portfolio_returns import (
    calculate_drawdown,
    calculate_sector_exposure,
    modified_dietz_return,
    portfolio_summary,
    time_weighted_return,
)
from src.common.config import settings
from src.common.models import PositionLot


def test_modified_dietz_with_midpoint_cashflow() -> None:
    """期初 100，期中投入 10，期末 120。

    Modified Dietz = (120 - 100 - 10) / (100 + 10 * 0.5) = 10 / 105 ≈ 9.52%.
    """
    ret = modified_dietz_return(
        begin_value=Decimal("100"),
        end_value=Decimal("120"),
        cash_flows=[(date(2026, 6, 15), Decimal("10"))],
        begin_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )
    assert ret is not None
    assert ret.quantize(Decimal("0.0001")) == Decimal("0.0951")


def test_modified_dietz_no_cashflow() -> None:
    ret = modified_dietz_return(
        begin_value=Decimal("100"),
        end_value=Decimal("110"),
        cash_flows=[],
    )
    assert ret == Decimal("0.1000")


def test_time_weighted_return_two_periods() -> None:
    """两期组合价值：期初 100，期中投入 10 后价值 120，期末 130。

    HPR1 = (120 - 10) / 100 = 1.10
    HPR2 = 130 / 120 = 1.0833...
    TWRR = 1.10 * 1.0833... - 1 = 19.17%.
    """
    ret = time_weighted_return(
        valuations=[
            (date(2026, 6, 1), Decimal("100")),
            (date(2026, 6, 15), Decimal("120")),
            (date(2026, 6, 30), Decimal("130")),
        ],
        cash_flows=[(date(2026, 6, 15), Decimal("10"))],
    )
    assert ret is not None
    assert ret.quantize(Decimal("0.0001")) == Decimal("0.1917")


def test_time_weighted_return_insufficient_valuations() -> None:
    ret = time_weighted_return(
        valuations=[(date(2026, 6, 1), Decimal("100"))],
        cash_flows=[],
    )
    assert ret is None


def test_calculate_drawdown() -> None:
    values = [
        Decimal("100"),
        Decimal("110"),
        Decimal("105"),
        Decimal("90"),
        Decimal("95"),
    ]
    dd = calculate_drawdown(values)
    assert dd == Decimal("0.1818")  # (110 - 90) / 110


def test_calculate_sector_exposure(tmp_path: Path) -> None:
    """行业暴露计算应读取证券主数据表。"""
    # 临时构造 security_master.json
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    master_json = web_public / "security-master.json"
    original = master_json.read_text(encoding="utf-8") if master_json.exists() else None
    try:
        master_json.write_text(
            json.dumps(
                [
                    {"ticker": "000725.SZ", "sector": "电子"},
                    {"ticker": "600519.SH", "sector": "食品饮料"},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        positions = [
            PositionLot(
                ticker="000725.SZ",
                quantity=100,
                cost_basis=Decimal("5"),
                market_price=Decimal("6"),
                market_value=Decimal("600"),
                unrealized_pnl=Decimal("100"),
            ),
            PositionLot(
                ticker="600519.SH",
                quantity=1,
                cost_basis=Decimal("1500"),
                market_price=Decimal("2000"),
                market_value=Decimal("2000"),
                unrealized_pnl=Decimal("500"),
            ),
        ]
        exposure = calculate_sector_exposure(positions)
        by_sector = {e.category: e.value_pct for e in exposure}
        assert by_sector["电子"] == Decimal("23.08")
        assert by_sector["食品饮料"] == Decimal("76.92")
    finally:
        if original is not None:
            master_json.write_text(original, encoding="utf-8")
        elif master_json.exists():
            master_json.unlink()


def test_portfolio_summary_aggregation() -> None:
    positions = [
        PositionLot(
            ticker="000725.SZ",
            quantity=100,
            cost_basis=Decimal("5"),
            market_price=Decimal("6"),
            market_value=Decimal("600"),
            unrealized_pnl=Decimal("100"),
            realized_pnl=Decimal("20"),
        ),
    ]
    summary = portfolio_summary(positions, realized_pnl=Decimal("20"), cash=Decimal("1000"))
    assert summary["total_market_value"] == Decimal("600")
    assert summary["total_assets"] == Decimal("1600")
    assert summary["unrealized_pnl"] == Decimal("100")
    assert summary["realized_pnl"] == Decimal("20")
