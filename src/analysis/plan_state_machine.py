"""交易计划状态机。

所有状态迁移必须经用户确认，并形成新的 plan_version。
"""

from datetime import datetime

from src.common.logger import get_logger
from src.common.models import PlanAuditLogEntry, TradePlan, TradePlanStatus

logger = get_logger(__name__)


class PlanStateMachineError(Exception):
    """状态机非法操作异常。"""


class PlanStateMachine:
    """管理 ``TradePlan`` 状态迁移与审计日志。"""

    # 合法迁移有向图
    _TRANSITIONS: dict[TradePlanStatus, set[TradePlanStatus]] = {
        TradePlanStatus.DRAFT: {TradePlanStatus.ACTIVE},
        TradePlanStatus.ACTIVE: {
            TradePlanStatus.PARTIALLY_TRIGGERED,
            TradePlanStatus.FULLY_TRIGGERED,
            TradePlanStatus.ASSUMPTION_BROKEN,
        },
        TradePlanStatus.PARTIALLY_TRIGGERED: {
            TradePlanStatus.FULLY_TRIGGERED,
            TradePlanStatus.ASSUMPTION_BROKEN,
        },
        TradePlanStatus.FULLY_TRIGGERED: {TradePlanStatus.CLOSED},
        TradePlanStatus.ASSUMPTION_BROKEN: {TradePlanStatus.CLOSED},
        TradePlanStatus.CLOSED: {TradePlanStatus.REVIEWED},
        TradePlanStatus.REVIEWED: set(),
    }

    def __init__(self, plan: TradePlan) -> None:
        self.plan = plan

    def allowed_transitions(self) -> list[TradePlanStatus]:
        """返回当前状态下允许迁移到的所有状态。"""
        targets = self._TRANSITIONS.get(self.plan.status, set())
        return sorted(targets, key=lambda s: s.value)

    def can_transition(self, to_status: TradePlanStatus) -> bool:
        """检查给定目标状态是否允许从当前状态迁移。"""
        return to_status in self._TRANSITIONS.get(self.plan.status, set())

    def transition(
        self,
        to_status: TradePlanStatus,
        *,
        user_confirmed: bool,
        reason: str | None = None,
        new_version: str | None = None,
    ) -> TradePlan:
        """执行状态迁移，要求用户确认并形成新版本。

        Args:
            to_status: 目标状态。
            user_confirmed: 是否已由用户显式确认。未确认时抛出异常。
            reason: 迁移原因，写入审计日志。
            new_version: 显式指定新版本号；未提供时自动递增。

        Returns:
            更新后的 TradePlan（与 self.plan 同一对象）。

        Raises:
            PlanStateMachineError: 未确认或迁移不合法。
        """
        if not user_confirmed:
            raise PlanStateMachineError("状态迁移必须经用户确认")

        if not self.can_transition(to_status):
            raise PlanStateMachineError(
                f"无法从 {self.plan.status.value} 迁移到 {to_status.value}"
            )

        from_status = self.plan.status
        previous_version = self.plan.plan_version
        if new_version is None:
            new_version = self._bump_version(previous_version)

        self.plan.status = to_status
        self.plan.plan_version = new_version
        self.plan.updated_at = datetime.now()
        self.plan.audit_log.append(
            PlanAuditLogEntry(
                timestamp=datetime.now(),
                from_status=from_status,
                to_status=to_status,
                action=f"transition:{from_status.value}->{to_status.value}",
                user_confirmed=user_confirmed,
                reason=reason,
                previous_version=previous_version,
                new_version=new_version,
            )
        )
        logger.info(
            "Plan %s transitioned %s -> %s (v%s -> v%s)",
            self.plan.plan_id,
            from_status.value,
            to_status.value,
            previous_version,
            new_version,
        )
        return self.plan

    @staticmethod
    def _bump_version(version: str) -> str:
        """版本号递增：整数版本直接 +1，非整数后缀追加 -1。"""
        try:
            return str(int(version) + 1)
        except ValueError:
            return f"{version}-1"

    def activate(self, *, user_confirmed: bool, reason: str | None = None) -> TradePlan:
        """便捷方法：草稿 -> 激活。"""
        return self.transition(
            TradePlanStatus.ACTIVE,
            user_confirmed=user_confirmed,
            reason=reason,
        )

    def close(self, *, user_confirmed: bool, reason: str | None = None) -> TradePlan:
        """便捷方法：完全触发 / 假设破坏 -> 关闭。"""
        return self.transition(
            TradePlanStatus.CLOSED,
            user_confirmed=user_confirmed,
            reason=reason,
        )

    def mark_reviewed(self, *, user_confirmed: bool, reason: str | None = None) -> TradePlan:
        """便捷方法：关闭 -> 复盘完成。"""
        return self.transition(
            TradePlanStatus.REVIEWED,
            user_confirmed=user_confirmed,
            reason=reason,
        )


def is_terminal_status(status: TradePlanStatus) -> bool:
    """判断是否为终态。"""
    return status == TradePlanStatus.REVIEWED


def status_display_name(status: TradePlanStatus) -> str:
    """返回状态中文展示名。"""
    mapping = {
        TradePlanStatus.DRAFT: "草稿",
        TradePlanStatus.ACTIVE: "激活",
        TradePlanStatus.PARTIALLY_TRIGGERED: "部分触发",
        TradePlanStatus.FULLY_TRIGGERED: "完全触发",
        TradePlanStatus.ASSUMPTION_BROKEN: "假设被破坏",
        TradePlanStatus.CLOSED: "关闭",
        TradePlanStatus.REVIEWED: "复盘完成",
    }
    return mapping.get(status, status.value)
