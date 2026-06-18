# 系统入口为自然语言 + Web，CLI 只作 agent worker，真实交易必须手动录入

用户入口以自然语言对话和 Web 前端为主，Python CLI 不直接面向用户，只作为 agent 背后的确定性 worker 完成数据库读写、快照生成、任务创建和产物校验。典型入口包括「分析 000725」「收盘巡检」「复核交易计划」等自然语言指令或 Web 按钮。一键巡检（如用户说「climbing」或点击「今日巡检」）由 agent 调度 Python worker 更新行情、市场、板块、持仓市值和计划触发状态，生成 MarketSnapshot、PortfolioSnapshot 和快速 DailyReviewSnapshot；巡检结束后只提示需要复核的股票、偏离的计划和过期的数据，不自动生成 ResearchSnapshot 或修改交易计划。录入交易流水、生成/更新 ResearchSnapshot、激活交易计划、修改计划版本必须由用户唤醒和确认。风险约束采用软性提醒，不硬性拦截。Skill 目录统一收敛到 `skills/`，并按 Climbing 上下文拆分为 `stock-research/`、`data-refresh/`、`daily-review/`、`trade-plan/`、`plan-review/`、`capital-flow/`。

## 状态

accepted

## 考虑的替代方案

1. **CLI 作为主要入口**：rejected。用户不会手动执行 Python CLI，且 agent-first 的体验更自然。
2. **原封不动复用 equity-researcher skill**：rejected。原始 skill 包含自己的数据源获取、用户确认和 Tear Sheet / Equity Report 选择流程，与 Climbing 的数据库、快照、任务状态和用户决策上下文不兼容。
3. **硬风控（仓位上限、现金下限等）**：rejected。用户资金量不大（10-15 万），实际操作中可能满仓或补充资金，硬性限制会阻碍正常使用。
4. **计划触发后自动修改持仓或自动下单**：rejected。系统边界明确不做自动交易，真实持仓变更只能来自用户手动录入流水。

## 后果

- 需要为 agent 设计自然语言意图路由和 Web 前端页面（Dashboard、个股分析、持仓、计划、宏观月报、巡检中心）。
- Python CLI 需要暴露稳定的 worker 命令（如 `update daily`、`analyze`、`plan review`），供 agent 调用而不是用户直接调用。
- 需要明确区分「巡检（只生成快照和提示）」和「复核（用户确认后生成/修改分析或计划）」两种模式。
- Skill 需要按 Climbing 的 job/context/schema 约定重写，避免重复询问用户。

---
