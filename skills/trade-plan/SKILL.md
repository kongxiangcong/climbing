# trade-plan

## 概要

本 Skill 用于基于 `ResearchSnapshot`、`MarketSnapshot`、`PortfolioSnapshot` 等上下文生成结构化交易计划草案（`TradePlan`）。

Climbing Python worker 通过 Kimi CLI 调用本 skill：

```bash
kimi --skills-dir skills/trade-plan --prompt "请为 000725.SZ 生成交易计划草案" --output-format stream-json
```

调用时会在 prompt 末尾附加 `[context]`，包含：
- `research_snapshot`：最新 `ResearchSnapshot` 的 JSON 表示
- `market_snapshot`：最新 `MarketSnapshot` 的 JSON 表示
- `portfolio_snapshot`：最新 `PortfolioSnapshot` 的 JSON 表示

## 输出 Schema

Skill 输出必须是可解析的 JSON，字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 计划名称 |
| `direction` | "long" / "short" | 方向 |
| `time_window` | string | 时间窗口，如 "3-6m" |
| `research_version` | string | 关联的 ResearchSnapshot 版本 |
| `entry_logic` | string | 入场逻辑 |
| `exit_logic` | string | 退出逻辑 |
| `target_price_low` | number | 目标价区间下限 |
| `target_price_high` | number | 目标价区间上限 |
| `stop_loss` | number | 止损价 |
| `take_profit` | number | 止盈价 |
| `position_limit` | number | 仓位上限 % |
| `initial_position_pct` | number | 首次建仓仓位 % |
| `max_position_pct` | number | 最大仓位 % |
| `risk_budget` | number | 风险预算 % |
| `expected_return` | number | 预期收益率 % |
| `invalidation_conditions` | list[string] | 失效条件 |
| `alternative_scenarios` | list[string] | 替代情景 |
| `triggers` | list[string] | 触发器 |
| `batch_strategy` | list[object] | 分批策略，每项含 `batch_id`、`target_price_low`、`target_price_high`、`allocation_pct`、`trigger_condition`、`notes` |
| `review_frequency` | string | 复盘频率，如 "weekly" |
| `notes` | string | 备注 |

状态、版本与审计日志由 Python worker 写入，skill 不输出：
- `status` 固定为 "draft"
- `plan_version` 固定为 "1"
- `audit_log` / `execution_records` / `linked_transaction_ids` 为空

## 当前阶段

Slice 6 目标：
- 目录结构与输出约定跑通。
- `TradePlan` schema 覆盖 PRD 中定义的核心字段。
- Python worker 在 Kimi CLI 不可用时使用 `tests/fixtures/trade_plan_draft.json` 作为 mock 输出，保证 CI 与离线环境可测试。

后续扩展：
- 接入真实行情/公告触发器检测，自动生成复核建议。
- 根据 PortfolioSnapshot 仓位风险动态调整仓位上限建议。
