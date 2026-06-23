"""交易流水标准化加载器。

支持券商/同花顺导出的 CSV/TSV（含 GBK 编码），统一转换为 ``Transaction`` 模型，
并在导入时与已有流水合并去重。
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

import csv

from src.common.logger import get_logger
from src.common.models import Transaction
from src.data_standardization.security_master import (
    UnrecognizedTickerError,
    standardize_ticker,
)

logger = get_logger(__name__)

# 列名别名 -> 标准列名
COLUMN_ALIASES: dict[str, set[str]] = {
    "ticker": {
        "ticker",
        "code",
        "symbol",
        "ts_code",
        "stock",
        "证券代码",
        "代码",
        "股票代码",
        "合约",
    },
    "side": {
        "side",
        "action",
        "direction",
        "type",
        "操作",
        "方向",
        "买卖",
        "side(direction)",
    },
    "quantity": {
        "quantity",
        "qty",
        "volume",
        "amount",
        "数量",
        "成交数量",
        "股数",
        "成交股数",
    },
    "price": {
        "price",
        "成交价格",
        "成交价",
        "价格",
        "成交单价",
        "cost",
    },
    "fee": {
        "fee",
        "fees",
        "commission",
        "手续费",
        "佣金",
        "费用",
        "交易费用",
    },
    "trade_date": {
        "trade_date",
        "date",
        "trading_day",
        "time",
        "成交日期",
        "交易日期",
        "日期",
        "成交时间",
    },
    "account": {
        "account",
        "账户",
        "资金账号",
        "账号",
        "acct",
    },
    "name": {
        "name",
        "证券名称",
        "名称",
        "股票名称",
    },
    "notes": {
        "notes",
        "note",
        "备注",
        "说明",
        "comment",
    },
}

SIDE_BUY = {"buy", "b", "买入", "买", "buyin", "long"}
SIDE_SELL = {"sell", "s", "卖出", "卖", "sale", "cover"}


def _normalize_header(header: str) -> str:
    """表头归一化：去空格、转小写、统一全角半角。"""
    h = header.strip().lower()
    h = h.replace("（", "(").replace("）", ")")
    h = h.replace(" ", "").replace("　", "")
    return h


def _build_header_map(headers: Sequence[str]) -> dict[str, str]:
    """将原始表头映射到标准列名；返回 {canonical: original}。"""
    header_map: dict[str, str] = {}
    seen_canonical: set[str] = set()
    for raw in headers:
        norm = _normalize_header(raw)
        for canonical, aliases in COLUMN_ALIASES.items():
            if norm in aliases and canonical not in seen_canonical:
                header_map[canonical] = raw
                seen_canonical.add(canonical)
                break
    return header_map


def _detect_encoding(path: Path) -> str:
    """检测文件编码，优先 UTF-8-sig，失败则回退 GB18030。"""
    for enc in ("utf-8-sig", "gb18030", "gbk"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    logger.warning("无法识别编码，回退 GB18030: %s", path)
    return "gb18030"


def _detect_delimiter(path: Path, encoding: str) -> str:
    """根据扩展名和首行内容判断分隔符。"""
    if path.suffix.lower() == ".tsv":
        return "\t"
    with path.open("r", encoding=encoding, newline="") as f:
        first_line = f.readline()
    if "\t" in first_line:
        return "\t"
    return ","


def _parse_date(value: str) -> date:
    """解析常见日期格式。"""
    value = value.strip().split()[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期：{value}")


def _parse_decimal(value: str | None, default: Decimal = Decimal("0")) -> Decimal:
    """解析 Decimal，失败时返回默认值。"""
    if value is None or str(value).strip() == "":
        return default
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"无法解析数值：{value}") from exc


def _parse_side(value: str) -> str:
    """统一交易方向为 buy / sell。"""
    norm = value.strip().lower()
    # 简单处理中文“买入/卖出”
    if "买入" in norm or "买" == norm or norm in SIDE_BUY:
        return "buy"
    if "卖出" in norm or "卖" == norm or norm in SIDE_SELL:
        return "sell"
    raise ValueError(f"无法识别交易方向：{value}")


def load_transactions(
    path: Path,
    encoding: str | None = None,
    raw_source: str | None = None,
) -> list[Transaction]:
    """从 CSV/TSV 加载并标准化交易流水。

    返回按 ``trade_date`` 升序排列的交易列表。
    """
    if not path.exists():
        raise FileNotFoundError(f"交易流水文件不存在：{path}")

    enc = encoding or _detect_encoding(path)
    delimiter = _detect_delimiter(path, enc)

    transactions: list[Transaction] = []
    unrecognized: list[str] = []

    with path.open("r", encoding=enc, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("CSV 表头为空")

        header_map = _build_header_map(reader.fieldnames)
        required = {"ticker", "side", "quantity", "price", "trade_date"}
        missing = required - set(header_map.keys())
        if missing:
            raise ValueError(
                f"缺少必要列：{missing}。识别到的列：{list(header_map.keys())}"
            )

        for idx, row in enumerate(reader, start=2):
            try:
                raw_ticker = row[header_map["ticker"]].strip()
                normalized_ticker, _, _ = standardize_ticker(raw_ticker)
            except UnrecognizedTickerError as exc:
                unrecognized.append(f"第 {idx} 行: {exc.args[0]}")
                continue

            try:
                side = _parse_side(row[header_map["side"]])
                quantity = int(_parse_decimal(row[header_map["quantity"]]))
                price = _parse_decimal(row[header_map["price"]])
                fee = _parse_decimal(
                    row.get(header_map.get("fee", ""), "") if "fee" in header_map else ""
                )
                trade_date = _parse_date(row[header_map["trade_date"]])
                account = (
                    row[header_map["account"]].strip()
                    if "account" in header_map
                    else "default"
                )
                name = (
                    row[header_map["name"]].strip() if "name" in header_map else None
                )
                notes = (
                    row[header_map["notes"]].strip() if "notes" in header_map else None
                )
            except (ValueError, KeyError) as exc:
                raise ValueError(f"第 {idx} 行解析失败：{exc}") from exc

            if quantity <= 0:
                raise ValueError(f"第 {idx} 行成交数量必须大于 0")

            transactions.append(
                Transaction(
                    ticker=normalized_ticker,
                    side=side,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    trade_date=trade_date,
                    account=account or "default",
                    name=name,
                    notes=notes,
                    raw_source=raw_source or str(path),
                )
            )

    if unrecognized:
        raise UnrecognizedTickerError(
            "以下代码无法自动识别，请确认后重试：\n" + "\n".join(unrecognized)
        )

    transactions.sort(key=lambda t: (t.trade_date, t.ticker))
    return transactions


def deduplicate_transactions(transactions: list[Transaction]) -> list[Transaction]:
    """按关键字段去重，保留首次出现。"""
    seen: OrderedDict[tuple[Any, ...], Transaction] = OrderedDict()
    for tx in transactions:
        key = (
            tx.ticker,
            tx.trade_date.isoformat(),
            tx.side,
            tx.quantity,
            str(tx.price),
            tx.account,
        )
        if key not in seen:
            seen[key] = tx
    return list(seen.values())


def merge_with_existing(
    new_transactions: list[Transaction],
    existing_path: Path,
) -> list[Transaction]:
    """将新流水与本地已有流水合并去重。"""
    existing: list[Transaction] = []
    if existing_path.exists():
        existing = load_transactions(existing_path, raw_source=str(existing_path))
    combined = existing + new_transactions
    return deduplicate_transactions(combined)


def save_transactions(transactions: list[Transaction], path: Path) -> None:
    """将标准化后的交易流水写入 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "ticker",
        "side",
        "quantity",
        "price",
        "fee",
        "trade_date",
        "account",
        "name",
        "notes",
        "raw_source",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for tx in transactions:
            writer.writerow(
                {
                    "ticker": tx.ticker,
                    "side": tx.side,
                    "quantity": tx.quantity,
                    "price": str(tx.price),
                    "fee": str(tx.fee),
                    "trade_date": tx.trade_date.isoformat(),
                    "account": tx.account,
                    "name": tx.name or "",
                    "notes": tx.notes or "",
                    "raw_source": tx.raw_source or "",
                }
            )
    logger.info("Saved %d transactions -> %s", len(transactions), path)
