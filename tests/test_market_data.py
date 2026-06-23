"""市场数据标准化模块测试。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from src.data_standardization.market_data import (
    FixtureMarketProvider,
    _parse_retrieved_at,
    fetch_market_data,
    normalize_market_data,
)


class TestFixtureMarketProvider:
    def test_fetch_returns_standardized_fields(self) -> None:
        provider = FixtureMarketProvider()
        data = provider.fetch(trade_date=date(2026, 6, 23))
        assert data is not None
        assert data["source"] == provider.name
        assert data["tier"] == provider.tier
        assert "retrieved_at" in data
        assert data["trade_date"] == "2026-06-23"
        assert data["indices"]
        assert data["breadth"]
        assert data["total_turnover"] is not None
        assert data["sector_heat"]
        assert data["margin_balance"] is not None
        assert data["northbound_flow"] is not None
        assert data["sentiment_score"] is not None
        assert data["risk_appetite"] is not None


class TestParseRetrievedAt:
    def test_parses_iso_string(self) -> None:
        assert _parse_retrieved_at("2026-06-23T15:00:00") == datetime(2026, 6, 23, 15, 0, 0)

    def test_parses_unix_timestamp(self) -> None:
        dt = _parse_retrieved_at(1719123456)
        assert isinstance(dt, datetime)

    def test_parses_datetime_object(self) -> None:
        dt = datetime(2026, 6, 23, 15, 0, 0)
        assert _parse_retrieved_at(dt) is dt

    def test_defaults_to_now_on_unknown_format(self) -> None:
        dt = _parse_retrieved_at("not-a-date")
        assert isinstance(dt, datetime)


class TestNormalizeMarketData:
    def test_normalizes_fields(self) -> None:
        raw = {
            "trade_date": "2026-06-23",
            "indices": [
                {"ticker": "000001.SH", "name": "上证指数", "close": 3000, "change_pct": 0.5, "volume": 100}
            ],
            "breadth": {"advancers": 2000, "decliners": 1500, "unchanged": 300},
            "total_turnover": 8000000000,
            "sector_heat": [{"name": "科技", "score": 85, "change_pct": 1.2}],
            "margin_balance": 15000000000,
            "northbound_flow": 1200000000,
            "etf_flow": {"510300.SH": 50000000},
            "sentiment_score": 0.6,
            "risk_appetite": "中性",
            "source": "test",
            "retrieved_at": "2026-06-23T15:00:00",
        }
        normalized = normalize_market_data(raw)
        assert normalized["trade_date"] == date(2026, 6, 23)
        assert normalized["indices"][0]["close"] == Decimal("3000")
        assert normalized["indices"][0]["change_pct"] == Decimal("0.5")
        assert normalized["breadth"]["advancers"] == 2000
        assert normalized["total_turnover"] == Decimal("8000000000")
        assert normalized["sector_heat"][0]["score"] == 85.0
        assert normalized["margin_balance"] == Decimal("15000000000")
        assert normalized["northbound_flow"] == Decimal("1200000000")
        assert normalized["etf_flow"]["510300.SH"] == Decimal("50000000")
        assert normalized["sentiment_score"] == 0.6
        assert normalized["metadata"].source == "test"

    def test_skips_none_etf_flow_values(self) -> None:
        raw = {
            "trade_date": "2026-06-23",
            "indices": [],
            "breadth": {},
            "total_turnover": 0,
            "sector_heat": [],
            "margin_balance": None,
            "northbound_flow": None,
            "etf_flow": {"510300.SH": 50000000, "510500.SH": None},
            "sentiment_score": 0.5,
            "risk_appetite": "中性",
            "source": "test",
            "retrieved_at": "2026-06-23T15:00:00",
        }
        normalized = normalize_market_data(raw)
        assert "510300.SH" in normalized["etf_flow"]
        assert "510500.SH" not in normalized["etf_flow"]

    def test_defaults_missing_index_prices_to_zero(self) -> None:
        raw = {
            "trade_date": "2026-06-23",
            "indices": [
                {"ticker": "000001.SH", "name": "上证指数", "close": None, "change_pct": None, "volume": 100}
            ],
            "breadth": {},
            "total_turnover": 0,
            "sector_heat": [],
            "margin_balance": None,
            "northbound_flow": None,
            "etf_flow": {},
            "sentiment_score": 0.5,
            "risk_appetite": "中性",
            "source": "test",
            "retrieved_at": "2026-06-23T15:00:00",
        }
        normalized = normalize_market_data(raw)
        index = normalized["indices"][0]
        assert index["close"] == Decimal("0")
        assert index["change_pct"] == Decimal("0")


class TestFetchMarketData:
    def test_fetch_from_fixture_succeeds(self) -> None:
        data = fetch_market_data(trade_date=date(2026, 6, 23), providers=[FixtureMarketProvider()])
        assert data["indices"]
        assert data["metadata"].source == "climbing.fixture"

    def test_fetch_raises_when_no_provider_succeeds(self) -> None:
        class FailingProvider:
            @property
            def name(self) -> str:
                return "failing"

            @property
            def tier(self) -> int:
                return 3

            def fetch(self, trade_date: date | None = None) -> dict[str, Any] | None:
                return None

        with pytest.raises(RuntimeError, match="No market data provider succeeded"):
            fetch_market_data(providers=[FailingProvider()])  # type: ignore[list-item]
