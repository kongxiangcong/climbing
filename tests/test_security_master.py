"""证券主数据标准化测试。"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.common.models import Security
from src.data_standardization.security_master import (
    SecurityMaster,
    TickerRule,
    UnrecognizedTickerError,
    standardize_ticker,
)


class TestStandardizeTicker:
    """测试 A 股、ETF、可转债代码标准化规则。"""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # 上海主板
            ("600519", ("600519.SH", "SH", "stock")),
            ("600519.SH", ("600519.SH", "SH", "stock")),
            # 上海科创板
            ("688981", ("688981.SH", "SH", "stock")),
            ("688981.SH", ("688981.SH", "SH", "stock")),
            # 深圳主板
            ("000725", ("000725.SZ", "SZ", "stock")),
            ("000725.SZ", ("000725.SZ", "SZ", "stock")),
            # 深圳创业板
            ("300750", ("300750.SZ", "SZ", "stock")),
            ("300750.SZ", ("300750.SZ", "SZ", "stock")),
            # 中小板
            ("002594", ("002594.SZ", "SZ", "stock")),
            # 北京证券交易所
            ("835185", ("835185.BJ", "BJ", "stock")),
            ("835185.BJ", ("835185.BJ", "BJ", "stock")),
            # ETF
            ("510300", ("510300.SH", "SH", "etf")),
            ("510300.SH", ("510300.SH", "SH", "etf")),
            ("159915", ("159915.SZ", "SZ", "etf")),
            ("159915.SZ", ("159915.SZ", "SZ", "etf")),
            # 可转债
            ("110059", ("110059.SH", "SH", "convertible_bond")),
            ("110059.SH", ("110059.SH", "SH", "convertible_bond")),
            ("128136", ("128136.SZ", "SZ", "convertible_bond")),
            ("128136.SZ", ("128136.SZ", "SZ", "convertible_bond")),
        ],
    )
    def test_standardize_recognized_tickers(self, raw: str, expected: tuple[str, str, str]) -> None:
        assert standardize_ticker(raw) == expected

    def test_standardize_preserves_uppercase(self) -> None:
        assert standardize_ticker("000725.sz") == ("000725.SZ", "SZ", "stock")

    def test_standardize_rejects_inconsistent_suffix(self) -> None:
        with pytest.raises(UnrecognizedTickerError):
            standardize_ticker("000725.SH")

    def test_standardize_rejects_unknown_prefix(self) -> None:
        with pytest.raises(UnrecognizedTickerError):
            standardize_ticker("999999")

    def test_standardize_rejects_invalid_market_suffix(self) -> None:
        with pytest.raises(UnrecognizedTickerError):
            standardize_ticker("000725.HK")

    def test_longer_prefix_wins_for_etf(self) -> None:
        # 510300 应以 ETF 规则匹配，而不是被截断为两位前缀
        normalized, market, asset_class = standardize_ticker("510300")
        assert market == "SH"
        assert asset_class == "etf"
        assert normalized == "510300.SH"


class TestSecurityMaster:
    """测试 SecurityMaster 持久化与去重。"""

    def test_save_writes_required_columns(self, tmp_path: Path) -> None:
        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        securities = [
            Security(
                ticker="000725.SZ",
                name="京东方A",
                market="SZ",
                asset_class="stock",
                sector="电子",
                industry="显示器件",
                tags=["面板"],
            )
        ]
        path, version = master.save(securities, source="test")

        df = pd.read_parquet(path)
        required = {
            "ticker",
            "name",
            "market",
            "asset_class",
            "sector",
            "industry",
            "tags",
            "source",
            "retrieved_at",
            "version",
        }
        assert required.issubset(set(df.columns))
        assert df["ticker"].iloc[0] == "000725.SZ"
        assert df["source"].iloc[0] == "test"
        assert df["version"].notna().all()

    def test_load_returns_empty_dataframe_with_required_columns(self, tmp_path: Path) -> None:
        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        df = master.load()
        assert list(df.columns) == master.COLUMN_ORDER
        assert len(df) == 0

    def test_add_from_watchlist_standardizes_and_deduplicates(
        self, tmp_path: Path
    ) -> None:
        watchlist = tmp_path / "tickers.yaml"
        yaml.dump(
            {
                "watchlist": [
                    {"ticker": "000725", "name": "京东方A", "tags": ["面板"]},
                    {"ticker": "000725.SZ", "name": "京东方A", "tags": ["面板"]},
                    {"ticker": "510300", "name": "沪深300ETF", "tags": ["ETF"]},
                    {"ticker": "110059", "name": "浦发转债", "tags": ["可转债"]},
                ]
            },
            watchlist.open("w", encoding="utf-8"),
            allow_unicode=True,
        )

        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        path, securities, unrecognized, _version = master.add_from_watchlist(watchlist)

        assert len(unrecognized) == 0
        assert path is not None and path.exists()
        tickers = {s.ticker for s in securities}
        assert tickers == {"000725.SZ", "510300.SH", "110059.SH"}
        # 重复代码应被去重
        assert len(securities) == 3

        df = pd.read_parquet(path)
        assert len(df) == 3
        assert set(df["asset_class"]) == {"stock", "etf", "convertible_bond"}

    def test_add_from_watchlist_reports_unrecognized_codes(
        self, tmp_path: Path
    ) -> None:
        watchlist = tmp_path / "tickers.yaml"
        yaml.dump(
            {
                "watchlist": [
                    {"ticker": "000725", "name": "京东方A"},
                    {"ticker": "UNKNOWN", "name": "未知标的"},
                ]
            },
            watchlist.open("w", encoding="utf-8"),
            allow_unicode=True,
        )

        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        path, securities, unrecognized, _version = master.add_from_watchlist(watchlist)

        assert unrecognized == ["UNKNOWN"]
        # 未识别时不应写入文件
        assert path is not None and not path.exists()
        assert len(securities) == 1

    def test_add_from_watchlist_accepts_manual_tickers(self, tmp_path: Path) -> None:
        watchlist = tmp_path / "tickers.yaml"
        yaml.dump(
            {
                "watchlist": [
                    {"ticker": "UNKNOWN", "name": "未知标的"},
                ]
            },
            watchlist.open("w", encoding="utf-8"),
            allow_unicode=True,
        )

        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        manual = {"UNKNOWN": {"market": "SZ", "name": "手动标的", "asset_class": "stock"}}
        path, securities, unrecognized, _version = master.add_from_watchlist(
            watchlist, manual_tickers=manual
        )

        assert unrecognized == []
        assert len(securities) == 1
        assert securities[0].ticker == "UNKNOWN.SZ"
        assert securities[0].asset_class == "stock"
        assert path is not None and path.exists()

    def test_ticker_rules_cover_required_asset_classes(self) -> None:
        """确认规则表覆盖 A 股、ETF、可转债三类资产。"""
        from src.data_standardization.security_master import TICKER_RULES

        asset_classes = {rule.asset_class for rule in TICKER_RULES}
        assert {"stock", "etf", "convertible_bond"}.issubset(asset_classes)

    def test_add_from_watchlist_writes_json(self, tmp_path: Path) -> None:
        watchlist = tmp_path / "tickers.yaml"
        yaml.dump(
            {"watchlist": [{"ticker": "000725", "name": "京东方A"}]},
            watchlist.open("w", encoding="utf-8"),
            allow_unicode=True,
        )

        master = SecurityMaster()
        master.output_dir = tmp_path
        master.output_path = tmp_path / "security_master.parquet"
        master.json_path = tmp_path / "security_master.json"

        master.add_from_watchlist(watchlist)

        assert master.json_path.exists()
        data = pd.read_json(master.json_path, orient="records")
        assert len(data) == 1
        assert data["ticker"].iloc[0] == "000725.SZ"
