# 每日收盘更新采用 agent 调度 + Python worker 的快照工作流

「每天收盘一键更新」不是用户直接运行 Python CLI，而是用户通过自然语言（如「收盘更新」「复盘今天」）触发，由 agent 理解意图并调度流程，Python 作为确定性 worker 维护数据库、生成快照、校验产物和调用后续分析任务。快照分为三层：MarketSnapshot（市场事实）、PortfolioSnapshot（账户事实）、DailyReviewSnapshot（agent 分析输出）。执行顺序为：更新市场数据 → MarketSnapshot → 刷新持仓 → PortfolioSnapshot → 检查计划触发器与 stale ResearchSnapshot → 生成复核 job → agent 生成 DailyReviewSnapshot。Python 只负责数据固化、去重、校验、版本化，不做市场判断。

## 状态

accepted

## 考虑的替代方案

1. **用户直接运行 Python CLI 完成全部更新**：rejected。无法整合自然语言意图、新闻解读、计划复核等需要 agent 综合判断的环节。
2. **MarketSnapshot / PortfolioSnapshot 也由 agent 生成**：rejected。账户市值、行业暴露、市场成交额等是确定性计算，由 Python 生成更可靠、可审计。
3. **DailyReviewSnapshot 由 Python 规则生成**：rejected。复盘需要综合多源信息做判断，agent 更适合。

## 后果

- 需要实现一个可被 agent 调用的 Python CLI 工作流，暴露为 `update daily` 等命令。
- MarketSnapshot 和 PortfolioSnapshot 必须有稳定的 schema 和版本字段，供 agent 消费。
- agent 需要知道何时生成 DailyReviewSnapshot、何时触发个股研报重跑、何时发起计划复核。

---
