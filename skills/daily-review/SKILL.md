# daily-review

## 用途

在每日收盘后生成 `DailyReviewSnapshot`，把市场事实、持仓事实、计划触发器结果和最新公告/新闻整合为一份复盘分析，供用户快速把握当日要点与待复核事项。

## 输入

调用方通过 context JSON 提供以下字段：

- `market_snapshot`: 最新的 `MarketSnapshot`（dict）。
- `portfolio_snapshot`: 最新的 `PortfolioSnapshot`（dict）。
- `plan_deviations`: 计划偏离告警列表，元素为 `{plan_id, reason, severity}`。
- `stale_research`: 需要重跑/过期的研究列表，元素为 `{ticker, reason}`。
- `latest_announcements`: 当日重点公告列表（可选）。
- `watchlist`: 明日关注清单（可选，字符串列表）。

## 输出

输出一份符合 `src/common/models.py` 中 `DailyReviewSnapshot` schema 的 JSON，必须包含：

- `highlights`: `list[str]` — 今日要点。
- `sentiment`: `str` — 市场情绪判断。
- `portfolio_risk`: `dict` — 持仓风险摘要。
- `plan_deviations`: `list[dict]` — 偏离计划列表。
- `stale_research`: `list[dict]` — 过期研究列表。
- `watchlist`: `list[str]` — 明日关注清单。

## 边界

- 本 skill 只生成分析快照，不修改交易计划、不修改持仓、不触发任何交易。
- 所有状态变更必须交由用户确认后由 `plan` / `portfolio` CLI 处理。
