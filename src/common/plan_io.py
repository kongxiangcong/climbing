"""交易计划持久化与前端摘要写入。"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.common.config import settings
from src.common.logger import get_logger
from src.common.models import PlanExecutionRecord, TradePlan
from src.common.paths import get_data_dir
from src.data_standardization.versioner import generate_version

logger = get_logger(__name__)


def plans_dir() -> Path:
    """返回计划文件目录并确保存在。"""
    path = get_data_dir("user") / "plans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def plan_path(plan_id: str) -> Path:
    """返回指定 plan_id 的 JSON 文件路径。"""
    return plans_dir() / f"{plan_id}.json"


def build_plan_id(ticker: str, name: str) -> str:
    """生成计划 ID：ticker-时间戳-哈希前缀。"""
    version_prefix = generate_version(f"{ticker}-{name}")[:14]
    return f"{ticker}-{version_prefix}"


def list_plan_ids() -> list[str]:
    """返回所有 plan_id 列表，按文件名排序。"""
    return sorted(p.stem for p in plans_dir().glob("*.json"))


def load_plan(plan_id: str) -> TradePlan:
    """从磁盘读取 TradePlan；不存在时抛出 FileNotFoundError。"""
    path = plan_path(plan_id)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return TradePlan.model_validate(data)


def save_plan(plan: TradePlan) -> Path:
    """将 TradePlan 写入磁盘，返回文件路径。"""
    path = plan_path(plan.plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    plan.updated_at = datetime.now()
    path.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved plan %s -> %s", plan.plan_id, path)
    return path


def write_plans_web_summary() -> Path:
    """将计划列表摘要写入 web/public/plans.json，供前端静态读取。"""
    web_public = settings.project_root / "web" / "public"
    web_public.mkdir(parents=True, exist_ok=True)
    web_path = web_public / "plans.json"

    summaries: list[dict[str, Any]] = []
    for plan_id in list_plan_ids():
        try:
            plan = load_plan(plan_id)
            summaries.append(
                {
                    "plan_id": plan.plan_id,
                    "name": plan.name,
                    "ticker": plan.ticker,
                    "direction": plan.direction,
                    "status": plan.status.value,
                    "status_display": _status_display(plan.status.value),
                    "plan_version": plan.plan_version,
                    "target_price_low": str(plan.target_price_low)
                    if plan.target_price_low is not None
                    else None,
                    "target_price_high": str(plan.target_price_high)
                    if plan.target_price_high is not None
                    else None,
                    "position_limit": str(plan.position_limit),
                    "risk_budget": str(plan.risk_budget),
                    "review_frequency": plan.review_frequency,
                    "research_version": plan.research_version,
                    "updated_at": plan.updated_at.isoformat(),
                }
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to summarize plan %s: %s", plan_id, exc)

    payload = {
        "last_updated_at": datetime.now().isoformat(),
        "count": len(summaries),
        "plans": summaries,
    }
    web_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote plans web summary -> %s", web_path)
    return web_path


def _status_display(status_value: str) -> str:
    """状态值中文映射。"""
    mapping = {
        "draft": "草稿",
        "active": "激活",
        "partially_triggered": "部分触发",
        "fully_triggered": "完全触发",
        "assumption_broken": "假设被破坏",
        "closed": "关闭",
        "reviewed": "复盘完成",
    }
    return mapping.get(status_value, status_value)


def link_transaction_to_plan(
    plan: TradePlan,
    transaction_id: str,
    ticker: str,
    side: str,
    quantity: int,
    price: Any,
    fee: Any = Decimal("0"),
    notes: str | None = None,
) -> TradePlan:
    """将一条真实交易流水关联到计划，并追加执行记录（不修改状态）。"""
    if transaction_id not in plan.linked_transaction_ids:
        plan.linked_transaction_ids.append(transaction_id)

    plan.execution_records.append(
        PlanExecutionRecord(
            transaction_id=transaction_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=Decimal(str(price)),
            fee=Decimal(str(fee)),
            notes=notes,
        )
    )
    plan.updated_at = datetime.now()
    return plan
