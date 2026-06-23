"""市场数据标准化模块。

职责：
- 从 fixture 或可选数据源拉取 A 股市场事实数据。
- 统一输出包含指数、市场宽度、成交额、板块热度、两融、北向、ETF 资金流、情绪评分等字段的字典。
- 为每条数据记录 ``source``、``retrieved_at``、``tier``、``confidence`` 等元数据，便于后续审计。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import SourceMetadata

logger = get_logger(__name__)


class MarketDataProvider(ABC):
    """市场数据源抽象。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """提供者名称。"""

    @property
    @abstractmethod
    def tier(self) -> int:
        """权威层级，数字越小越权威。"""

    @abstractmethod
    def fetch(self, trade_date: date | None = None) -> dict[str, Any] | None:
        """拉取指定交易日的市场数据；失败时返回 None。"""


class FixtureMarketProvider(MarketDataProvider):
    """从本地 fixture 读取市场数据，作为测试与离线场景的默认来源。"""

    FIXTURE_NAME = "market_snapshot.json"

    @property
    def name(self) -> str:
        return "climbing.fixture"

    @property
    def tier(self) -> int:
        return 3

    def fetch(self, trade_date: date | None = None) -> dict[str, Any] | None:
        path = settings.project_root / "tests" / "fixtures" / self.FIXTURE_NAME
        if not path.exists():
            logger.warning("Market fixture not found: %s", path)
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if trade_date is not None:
            data["trade_date"] = trade_date.isoformat()
        data["source"] = self.name
        data["tier"] = self.tier
        data["retrieved_at"] = datetime.now().isoformat()
        return data


class AkshareMarketProvider(MarketDataProvider):
    """通过 akshare 拉取市场数据（可选，未安装时自动跳过）。"""

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def tier(self) -> int:
        return 3

    def fetch(self, trade_date: date | None = None) -> dict[str, Any] | None:
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError:
            logger.debug("akshare not installed, skipping")
            return None

        try:
            return self._fetch_impl(ak, trade_date)
        except Exception as exc:  # pragma: no cover
            logger.warning("akshare market data fetch failed: %s", exc)
            return None

    def _fetch_impl(self, ak: Any, trade_date: date | None) -> dict[str, Any] | None:  # pragma: no cover
        dt = trade_date or date.today()
        dt_str = dt.strftime("%Y%m%d")

        # 指数行情
        indices: list[dict[str, Any]] = []
        try:
            df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date=dt_str, end_date=dt_str)
            if not df.empty:
                row = df.iloc[-1]
                indices.append(
                    {
                        "ticker": "000001.SH",
                        "name": "上证指数",
                        "close": float(row["收盘"]),
                        "change_pct": float(row["涨跌幅"]),
                        "volume": int(row["成交量"]),
                    }
                )
        except Exception as exc:
            logger.warning("Failed to fetch SH index via akshare: %s", exc)

        return {
            "trade_date": dt.isoformat(),
            "indices": indices,
            "breadth": {"advancers": 0, "decliners": 0, "unchanged": 0},
            "total_turnover": 0.0,
            "sector_heat": [],
            "margin_balance": None,
            "northbound_flow": None,
            "etf_flow": {},
            "sentiment_score": None,
            "risk_appetite": None,
            "source": self.name,
            "tier": self.tier,
            "retrieved_at": datetime.now().isoformat(),
        }


class KimiDatasourceMarketProvider(MarketDataProvider):
    """通过 kimi-datasource 拉取市场数据（可选，未安装时自动跳过）。"""

    @property
    def name(self) -> str:
        return "kimi-datasource"

    @property
    def tier(self) -> int:
        return 3

    def fetch(self, trade_date: date | None = None) -> dict[str, Any] | None:
        try:
            from kimi_datasource import DataSource  # type: ignore
        except ImportError:
            logger.debug("kimi-datasource not installed, skipping")
            return None

        try:
            ds = DataSource()
            dt = trade_date or date.today()
            snapshot = ds.market_snapshot(trade_date=dt)
            result: dict[str, Any] = dict(snapshot)
            result.setdefault("source", self.name)
            result.setdefault("tier", self.tier)
            result.setdefault("retrieved_at", datetime.now().isoformat())
            return result
        except Exception as exc:  # pragma: no cover
            logger.warning("kimi-datasource market fetch failed: %s", exc)
            return None


DEFAULT_PROVIDERS: list[MarketDataProvider] = [
    FixtureMarketProvider(),
    KimiDatasourceMarketProvider(),
    AkshareMarketProvider(),
]


def _to_decimal(value: Any) -> Decimal | None:
    """将数值安全转换为 Decimal；None 保持 None。"""
    if value is None:
        return None
    return Decimal(str(value))


def _parse_retrieved_at(value: Any) -> datetime:
    """将多种可能的时间表示解析为 datetime。"""
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    value_str = str(value).strip()
    # 尝试 ISO 格式
    try:
        return datetime.fromisoformat(value_str)
    except ValueError:
        pass
    # 尝试 Unix 时间戳（整数或浮点数）
    try:
        timestamp = float(value_str)
        return datetime.fromtimestamp(timestamp)
    except ValueError:
        pass
    logger.warning("Unrecognized retrieved_at format: %r; using now", value)
    return datetime.now()


def _normalize_indices(raw_indices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统一指数指标字段类型；缺失或 None 时回退到 0 并记录日志。"""
    normalized: list[dict[str, Any]] = []
    for item in raw_indices:
        ticker = str(item.get("ticker", ""))
        close = _to_decimal(item.get("close"))
        change_pct = _to_decimal(item.get("change_pct"))
        if close is None:
            logger.warning("Index %s missing close price; defaulting to 0", ticker)
            close = Decimal("0")
        if change_pct is None:
            logger.warning("Index %s missing change_pct; defaulting to 0", ticker)
            change_pct = Decimal("0")
        normalized.append(
            {
                "ticker": ticker,
                "name": str(item.get("name", "")),
                "close": close,
                "change_pct": change_pct,
                "volume": item.get("volume"),
            }
        )
    return normalized


def _normalize_sector_heat(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统一板块热度字段类型。"""
    normalized: list[dict[str, Any]] = []
    for item in raw:
        normalized.append(
            {
                "name": str(item.get("name", "")),
                "score": float(item.get("score", 0)),
                "change_pct": _to_decimal(item.get("change_pct")),
            }
        )
    return normalized


def _normalize_etf_flow(raw: dict[str, Any]) -> dict[str, Decimal]:
    """统一 ETF 资金流字段类型；跳过 None 值。"""
    result: dict[str, Decimal] = {}
    for k, v in raw.items():
        decimal_value = _to_decimal(v)
        if decimal_value is None:
            logger.warning("ETF flow %s has None value; skipping", k)
            continue
        result[k] = decimal_value
    return result


def fetch_market_data(
    trade_date: date | None = None,
    providers: list[MarketDataProvider] | None = None,
) -> dict[str, Any]:
    """拉取并标准化市场数据。

    按 ``providers`` 顺序尝试，返回第一个成功的结果；全部失败时抛出 ``RuntimeError``。
    默认优先使用本地 fixture，离线可用；若 fixture 缺失再尝试可选外部数据源。
    """
    providers = providers or DEFAULT_PROVIDERS
    for provider in providers:
        data = provider.fetch(trade_date)
        if data is not None:
            logger.info("Fetched market data from %s", provider.name)
            return normalize_market_data(data)
        logger.debug("Market provider %s returned no data", provider.name)

    raise RuntimeError("No market data provider succeeded")


def normalize_market_data(raw: dict[str, Any]) -> dict[str, Any]:
    """将原始市场数据标准化为 MarketSnapshot 可直接消费的字段。"""
    trade_date = raw.get("trade_date") or date.today().isoformat()
    if isinstance(trade_date, datetime):
        trade_date = trade_date.date().isoformat()

    breadth = raw.get("breadth", {})
    normalized_breadth = {
        "advancers": int(breadth.get("advancers", 0)),
        "decliners": int(breadth.get("decliners", 0)),
        "unchanged": int(breadth.get("unchanged", 0)),
    }

    metadata = SourceMetadata(
        source=str(raw.get("source", "unknown")),
        retrieved_at=_parse_retrieved_at(raw.get("retrieved_at")),
        version="1.0.0",
        tier=raw.get("tier"),
        confidence=raw.get("confidence"),
        notes=raw.get("notes"),
    )

    return {
        "trade_date": datetime.strptime(str(trade_date), "%Y-%m-%d").date(),
        "indices": _normalize_indices(raw.get("indices", [])),
        "breadth": normalized_breadth,
        "total_turnover": _to_decimal(raw.get("total_turnover")),
        "sector_heat": _normalize_sector_heat(raw.get("sector_heat", [])),
        "margin_balance": _to_decimal(raw.get("margin_balance")),
        "northbound_flow": _to_decimal(raw.get("northbound_flow")),
        "etf_flow": _normalize_etf_flow(raw.get("etf_flow", {})),
        "sentiment_score": float(raw["sentiment_score"]) if raw.get("sentiment_score") is not None else None,
        "risk_appetite": raw.get("risk_appetite"),
        "metadata": metadata,
    }


def build_market_snapshot_data(trade_date: date | None = None) -> dict[str, Any]:
    """对外主入口：拉取并返回标准化市场数据字典。"""
    return fetch_market_data(trade_date)
