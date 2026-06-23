# stock-research

## 概要

本 Skill 用于生成 A 股个股**深度研报**（Equity Report）。

与 `equity-researcher/` 不同，本 skill 仅保留“深度研报”单一模式：
- 不生成 Tear Sheet / 投资速览
- 不询问 L1 / L2 估值深度
- 默认由 Climbing Python worker 调用，AI 负责内容生成，Python 负责产物固化与 schema 校验

## 调用方式

Climbing Python worker 通过 Kimi CLI 调用本 skill：

```bash
kimi --skills-dir skills/stock-research --prompt "请生成 000725.SZ 的深度研报" --output-format stream-json
```

调用时会在 prompt 末尾附加 `[output_dir]`，指向 `data/reports/equity/{ticker}/{version}/`。

## 输出约定

必须在该目录下生成以下四个文件：

1. `snapshot.json` — 个股研报结构化快照，必须符合 `ResearchSnapshot` schema（见 `src/common/models.py`）。
2. `report.pdf` — PDF 研报，使用 `output/report.css` 样式。
3. `qa_check.json` — QA 结果，至少包含 `checks_passed`、`issues`、`checked_at`。
4. `references.json` — 引用与数据来源列表。

## 当前阶段（Skeleton）

当前 slice 为骨架阶段：
- 目录结构与输出约定优先跑通。
- 研报内容可为占位数据，但 `snapshot.json` 字段必须完整、schema 合规。
- Python worker 在 `--mock` 模式或 Kimi CLI 不可用时使用 fixture 数据，保证 CI 与离线环境可测试。

## 样式与布局

- CSS 单一来源：`output/report.css`，渲染 PDF 时必须完整嵌入 `<style>` 标签。
- 布局规范：`output/report-layout.md`。
- QA 规范：`output/qa_check.md`。

## ResearchSnapshot 必填字段

```json
{
  "snapshot_id": "research-{ticker}-{version}",
  "report_type": "research",
  "created_at": "2026-06-23T12:00:00",
  "version": "YYYYMMDDhhmmss-{hash_prefix}",
  "metadata": {
    "source": "skills/stock-research",
    "retrieved_at": "2026-06-23T12:00:00",
    "version": "1.0.0"
  },
  "ticker": "000725.SZ",
  "summary": "...",
  "six_dimensions": {...},
  "valuation": {"method": "...", "value_low": "...", "value_high": "...", "assumptions": []},
  "risks": [...],
  "assumptions": [...],
  "invalidation_conditions": [...],
  "target_price_low": "...",
  "target_price_high": "...",
  "pdf_path": ".../report.pdf",
  "references": [...]
}
```

## 后续扩展

- 在 `scripts/` 增加图表生成与 report validator。
- 在 `references/` 补充数据源优先级、财务模型规范。
- 逐步将 `equity-researcher/` 的分析模块（六维分析、估值、风险框架）迁移到本 skill。
