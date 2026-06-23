"""证券主数据标准化。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import Security, SourceMetadata
from src.common.paths import get_data_dir
from src.data_standardization.versioner import generate_version

logger = get_logger(__name__)


class UnrecognizedTickerError(ValueError):
    """当代码无法自动识别时抛出。"""


@dataclass(frozen=True)
class TickerRule:
    """证券代码前缀匹配规则。"""

    market: str
    asset_class: str
    prefixes: tuple[str, ...]


# A 股、ETF、可转债代码前缀规则。
# 规则按优先级排列，同一市场内较长前缀优先匹配。
TICKER_RULES: list[TickerRule] = [
    # 上海主板 / 科创板 / B 股
    TickerRule("SH", "stock", ("600", "601", "603", "605")),
    TickerRule("SH", "stock", ("688", "689")),  # 科创板
    TickerRule("SH", "stock", ("900",)),  # B 股
    # 上海 ETF / 场内基金
    TickerRule("SH", "etf", ("510", "511", "512", "513", "518")),
    TickerRule("SH", "etf", ("50", "51")),  # 兼容两位前缀
    # 上海可转债
    TickerRule("SH", "convertible_bond", ("110", "113", "132")),
    # 深圳主板 / 中小板 / 创业板 / B 股
    TickerRule("SZ", "stock", ("000", "001", "002", "003")),
    TickerRule("SZ", "stock", ("300", "301")),  # 创业板
    TickerRule("SZ", "stock", ("200",)),  # B 股
    # 深圳 ETF / 场内基金
    TickerRule("SZ", "etf", ("159", "150", "160", "169")),
    TickerRule("SZ", "etf", ("15", "16")),  # 兼容两位前缀
    # 深圳可转债
    TickerRule("SZ", "convertible_bond", ("123", "127", "128")),
    # 北京证券交易所
    TickerRule("BJ", "stock", ("82", "83", "87", "88")),
    TickerRule("BJ", "stock", ("4", "8")),
]


def _match_rule(code: str) -> TickerRule | None:
    """根据代码前缀匹配规则，较长前缀优先。"""
    code = code.strip()
    for rule in TICKER_RULES:
        for prefix in rule.prefixes:
            if code.startswith(prefix):
                return rule
    return None


def standardize_ticker(raw_ticker: str) -> tuple[str, str, str]:
    """标准化证券代码。

    输入可以是 ``000725`` 或 ``000725.SZ``，输出统一为 ``CODE.MARKET`` 形式，
    同时返回 ``(market, asset_class)``。

    无法识别时抛出 :class:`UnrecognizedTickerError`。
    """
    raw_ticker = raw_ticker.strip().upper()
    if not raw_ticker:
        raise UnrecognizedTickerError("证券代码不能为空。")

    if "." in raw_ticker:
        code, suffix = raw_ticker.rsplit(".", 1)
        code = code.strip()
        suffix = suffix.strip().upper()
        if suffix not in {"SH", "SZ", "BJ"}:
            raise UnrecognizedTickerError(
                f"无法识别市场后缀：{raw_ticker}。请使用 SH / SZ / BJ。"
            )
        rule = _match_rule(code)
        if rule is None:
            raise UnrecognizedTickerError(
                f"无法识别证券代码：{raw_ticker}。请通过 "
                f"--manual-ticker CODE:MARKET:NAME[:ASSET_CLASS] 指定。"
            )
        if rule.market != suffix:
            raise UnrecognizedTickerError(
                f"代码后缀与自动识别市场不一致：{raw_ticker}，"
                f"前缀识别为 {rule.market}。"
            )
        return f"{code}.{suffix}", rule.market, rule.asset_class

    rule = _match_rule(raw_ticker)
    if rule is None:
        raise UnrecognizedTickerError(
            f"无法识别证券代码：{raw_ticker}。请提供带后缀代码（如 000725.SZ）"
            f"或通过 --manual-ticker {raw_ticker}:MARKET:NAME 指定。"
        )
    return f"{raw_ticker}.{rule.market}", rule.market, rule.asset_class


class SecurityMaster:
    """证券主数据表管理。"""

    TABLE_NAME = "security_master.parquet"
    JSON_NAME = "security_master.json"

    COLUMN_ORDER = [
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
    ]

    def __init__(self) -> None:
        self.output_dir = get_data_dir("standardized")
        self.output_path = self.output_dir / self.TABLE_NAME
        self.json_path = self.output_dir / self.JSON_NAME

    def load(self) -> pd.DataFrame:
        """加载证券主数据表。"""
        if self.output_path.exists():
            df = pd.read_parquet(self.output_path)
            for col in self.COLUMN_ORDER:
                if col not in df.columns:
                    df[col] = None
            return cast(pd.DataFrame, df[self.COLUMN_ORDER])
        return pd.DataFrame(columns=self.COLUMN_ORDER)

    def save(self, securities: list[Security], source: str = "config/tickers.yaml") -> tuple[Path, str]:
        """保存证券主数据表为 Parquet，同时输出 JSON 副本供前端读取。

        返回 ``(output_path, version)``。
        """
        version = generate_version([s.model_dump() for s in securities])
        now = datetime.now()

        records: list[dict[str, Any]] = []
        for s in securities:
            record = s.model_dump(exclude={"metadata"})
            record["source"] = source
            record["retrieved_at"] = now
            record["version"] = version
            records.append(record)

        df = pd.DataFrame(records)
        for col in self.COLUMN_ORDER:
            if col not in df.columns:
                df[col] = None
        df = df[self.COLUMN_ORDER]

        df.to_parquet(self.output_path, index=False)
        df.to_json(self.json_path, orient="records", force_ascii=False, indent=2)
        logger.info("Saved security master: %s rows -> %s", len(df), self.output_path)
        return self.output_path, version

    def add_from_watchlist(
        self,
        watchlist_path: Path | None = None,
        manual_tickers: dict[str, dict[str, Any]] | None = None,
        dry_run: bool = False,
    ) -> tuple[Path | None, list[Security], list[str], str | None]:
        """从 watchlist 配置文件加载关注列表并写入证券主数据表。

        返回 ``(output_path, securities, unrecognized_tickers, version)``。
        ``output_path`` 和 ``version`` 为 ``None`` 当且仅当未识别代码存在或处于 dry_run 模式。
        """
        if watchlist_path is None:
            watchlist_path = Path(settings.project_root) / "config" / "tickers.yaml"

        with watchlist_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        manual_tickers = manual_tickers or {}
        securities: list[Security] = []
        unrecognized: list[str] = []

        for item in data.get("watchlist", []):
            raw = str(item["ticker"]).strip()
            name = item.get("name") or raw
            code_only = raw.split(".")[0]
            manual_key = raw if raw in manual_tickers else code_only

            if manual_key in manual_tickers:
                manual = manual_tickers[manual_key]
                market = manual["market"].upper()
                normalized = raw if "." in raw else f"{raw}.{market}"
                securities.append(
                    Security(
                        ticker=normalized,
                        name=manual.get("name", name),
                        market=market,
                        asset_class=manual.get("asset_class", "stock"),
                        sector=item.get("sector"),
                        industry=item.get("industry"),
                        tags=item.get("tags", []),
                    )
                )
                continue

            try:
                normalized, market, asset_class = standardize_ticker(raw)
                securities.append(
                    Security(
                        ticker=normalized,
                        name=name,
                        market=market,
                        asset_class=asset_class,
                        sector=item.get("sector"),
                        industry=item.get("industry"),
                        tags=item.get("tags", []),
                    )
                )
            except UnrecognizedTickerError:
                unrecognized.append(raw)

        # 按 ticker 去重，保留第一次出现
        seen: set[str] = set()
        unique: list[Security] = []
        for s in securities:
            if s.ticker not in seen:
                seen.add(s.ticker)
                unique.append(s)

        if unrecognized:
            return self.output_path, unique, unrecognized, None

        if dry_run:
            return None, unique, [], None

        if not unique:
            logger.warning("No recognized securities in watchlist")
            path, version = self.save([])
        else:
            path, version = self.save(unique)

        return path, unique, [], version
