# plan-review

## 概要

本 Skill 用于在交易计划出现偏离时生成复核草案（`PlanReviewSnapshot` 的复核部分）。

它接收当前 `TradePlan`、关联的 `ResearchSnapshot` / `MarketSnapshot`、最新价格、以及 Python worker 已计算出的偏离结果（`triggered_conditions`、`score`、`level`），输出结构化的多空讨论、基本面/估值/市场复核、以及计划变更建议。

Climbing Python worker 通过 Kimi CLI 调用本 skill：

```bash
kimi --skills-dir skills/plan-review --prompt "请复核以下交易计划" --output-format stream-json
```

调用时会在 prompt 末尾附加 `[context]`，包含：

- `plan`：当前 `TradePlan` 的 JSON 表示
- `research_snapshot`：最新 `ResearchSnapshot` 的 JSON 表示（可选）
- `market_snapshot`：最新 `MarketSnapshot` 的 JSON 表示（可选）
- `latest_price`：最新价格
- `deviation_result`：Python worker 计算的偏离结果，包含 `triggered_conditions`、`score`、`level`、`action`

## 输出 Schema

Skill 输出必须是可解析的 JSON，字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `triggered_conditions` | list[string] | 已触发的条件列表，Python worker 会与其自身结果合并 |
| `deviations` | list[string] | 每条偏离的简要说明 |
| `recommendation` | string | 综合建议 |
| `suggested_action` | string | 建议的下一步操作 |
| `fundamental_review` | string | 基本面复核 |
| `valuation_review` | string | 估值复核 |
| `market_review` | string | 市场/情绪复核 |
| `bull_arguments` | list[string] | 多头论点 |
| `bear_arguments` | list[string] | 空头论点 |
| `plan_change_suggestions` | list[string] | 计划变更建议 |

以下字段由 Python worker 写入，skill 不输出：

- `snapshot_id`、`version`、`created_at`、`metadata`
- `plan_id`、`plan_version`
- `latest_price`、`requires_user_confirmation`、`user_decision`

## 当前阶段

Slice 7 目标：

- 建立 `skills/plan-review/` 目录结构与输出约定。
- 输出 schema 覆盖 PRD 中要求的“多空讨论、基本面/估值/市场复核、计划变更建议”。
- Python worker 在 Kimi CLI 不可时使用 `tests/fixtures/plan_review_draft.json` 作为 mock 输出，保证 CI 与离线环境可测试。

后续扩展：

- 接入真实公告/财报数据后，agent 可基于事实表做更深度的定性复核。
- 与 `PlanStateMachine` 联动，自动生成状态迁移建议。
