"""交易流水加载器测试。"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.data_standardization.security_master import UnrecognizedTickerError
from src.data_standardization.transaction_loader import (
    deduplicate_transactions,
    load_transactions,
    merge_with_existing,
    save_transactions,
)


def test_load_simple_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "tx.csv"
    csv_path.write_text(
        "ticker,side,quantity,price,trade_date,fee\n"
        "000725.SZ,buy,100,5.20,2026-06-20,5.00\n",
        encoding="utf-8-sig",
    )
    txs = load_transactions(csv_path)
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ticker == "000725.SZ"
    assert tx.side == "buy"
    assert tx.quantity == 100
    assert tx.price == Decimal("5.20")
    assert tx.fee == Decimal("5.00")
    assert tx.trade_date == date(2026, 6, 20)


def test_load_chinese_headers_and_tsv(tmp_path: Path) -> None:
    csv_path = tmp_path / "tx.tsv"
    csv_path.write_text(
        "证券代码\t操作\t数量\t成交价\t成交日期\t手续费\t账户\t备注\n"
        "000725.SZ\t买入\t100\t5.20\t2026-06-20\t5\tA1\t首次建仓\n",
        encoding="utf-8-sig",
    )
    txs = load_transactions(csv_path)
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ticker == "000725.SZ"
    assert tx.side == "buy"
    assert tx.account == "A1"
    assert tx.notes == "首次建仓"


def test_load_gbk_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "tx.csv"
    csv_path.write_bytes(
        "ticker,side,quantity,price,trade_date\n000725.SZ,buy,100,5.20,2026-06-20\n".encode(
            "gbk"
        )
    )
    txs = load_transactions(csv_path)
    assert len(txs) == 1
    assert txs[0].ticker == "000725.SZ"


def test_deduplicate_transactions_keeps_first() -> None:
    from src.common.models import Transaction

    txs = [
        Transaction(ticker="000725.SZ", side="buy", quantity=100, price=Decimal("5"), trade_date=date(2026, 6, 20)),
        Transaction(ticker="000725.SZ", side="buy", quantity=100, price=Decimal("5"), trade_date=date(2026, 6, 20)),
        Transaction(ticker="600519.SH", side="buy", quantity=10, price=Decimal("1500"), trade_date=date(2026, 6, 20)),
    ]
    result = deduplicate_transactions(txs)
    assert len(result) == 2


def test_merge_with_existing_appends_and_dedups(tmp_path: Path) -> None:
    existing = tmp_path / "existing.csv"
    existing.write_text(
        "ticker,side,quantity,price,trade_date,fee\n"
        "000725.SZ,buy,100,5.20,2026-06-20,5\n",
        encoding="utf-8-sig",
    )
    from src.common.models import Transaction

    new_txs = [
        Transaction(ticker="000725.SZ", side="buy", quantity=100, price=Decimal("5.20"), fee=Decimal("5"), trade_date=date(2026, 6, 20)),
        Transaction(ticker="600519.SH", side="buy", quantity=10, price=Decimal("1500"), trade_date=date(2026, 6, 20)),
    ]
    merged = merge_with_existing(new_txs, existing)
    assert len(merged) == 2
    tickers = {tx.ticker for tx in merged}
    assert tickers == {"000725.SZ", "600519.SH"}


def test_save_transactions_roundtrip(tmp_path: Path) -> None:
    from src.common.models import Transaction

    txs = [
        Transaction(ticker="000725.SZ", side="buy", quantity=100, price=Decimal("5.20"), fee=Decimal("5"), trade_date=date(2026, 6, 20)),
    ]
    out = tmp_path / "out.csv"
    save_transactions(txs, out)
    loaded = load_transactions(out)
    assert len(loaded) == 1
    assert loaded[0].ticker == "000725.SZ"


def test_load_unrecognized_ticker_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "tx.csv"
    csv_path.write_text(
        "ticker,side,quantity,price,trade_date\nUNKNOWN,buy,100,5.20,2026-06-20\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(UnrecognizedTickerError):
        load_transactions(csv_path)
