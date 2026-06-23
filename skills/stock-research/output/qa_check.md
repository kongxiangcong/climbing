# QA Checklist — Stock Research Skeleton

本文件定义 `skills/stock-research` 骨架阶段的最小 QA 检查项。

## A-Tier 检查（任何失败阻止交付）

1. `snapshot.json` 存在且为合法 JSON。
2. `snapshot.json` 可通过 `ResearchSnapshot` Pydantic schema 校验。
3. `report.pdf` 存在且以 `%PDF` 开头。
4. `qa_check.json` 存在且为合法 JSON。
5. `references.json` 存在且为合法 JSON。

## B-Tier 检查（骨架阶段记录即可）

1. PDF 页数 ≥ 1。
2. `summary` 字段非空。
3. `six_dimensions` 至少包含 3 个维度。
4. `risks` 列表非空。
5. `references` 列表非空。

## QA 输出格式

```json
{
  "checks_passed": true,
  "issues": [],
  "checked_at": "2026-06-23T12:00:00"
}
```

## 后续扩展

完整 QA 逻辑将逐步迁移 `equity-researcher/output/report-qa.md` 的 A/B/C tier 检查。
