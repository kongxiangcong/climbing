# stock-research

## 概要

本 Skill 用于生成 A 股个股**深度研报**（Equity Report）。

与 `equity-researcher/` 不同，本 skill 仅保留“深度研报”单一模式：
- 不生成 Tear Sheet / 投资速览
- 不询问 L1 / L2 估值深度（默认 L1，但允许在 prompt 中要求 L2 DCF）
- 默认由 Climbing Python worker 调用，AI 负责内容生成，Python 负责产物固化与 schema 校验

## 调用方式

Climbing Python worker 通过 Kimi CLI 调用本 skill：

```bash
kimi --skills-dir skills/stock-research --prompt "请生成 000725.SZ 的深度研报" --output-format stream-json
```

调用时会在 prompt 末尾附加 `[output_dir]`，指向 `data/reports/equity/{ticker}/{version}/`。

Skill 的输出必须是**可解析的 JSON**，包含 13 个 section（见下方“输出 Schema 映射”）。
Python worker 通过 `src/common/equity_researcher_adapter.py` 将其转换为 `ResearchSnapshot`。

## 分析框架

本 skill 引用以下分析模块（位于 `references/`）：

1. **六维分析** (`references/six-dimension-analysis.md`) — 核心分析框架 H1-H6
2. **投资逻辑** (`references/investment-logic.md`) — 短期/长期投资逻辑 + 投资论点综合分析表
3. **风险框架** (`references/risk-framework.md`) — 结构化风险评估
4. **可比估值** (`references/valuation-comparable.md`) — 可比公司估值（L1）
5. **DCF 与敏感性** (`references/dcf-and-sensitivity.md`) — DCF L2 估值与敏感性矩阵
6. **产业链** (`references/industry-chain.md`) — 产业链图谱规范
7. **表格规范** (`references/tables.md`) — 表格样式与数据源标注
8. **数据源** (`references/data-sources.md`) — 数据源优先级与权威层级

## 输出约定

必须在 `[output_dir]` 下生成以下四个文件：

1. `snapshot.json` — 个股研报结构化快照，必须符合 `ResearchSnapshot` schema（见 `src/common/models.py`）。
2. `report.pdf` — PDF 研报，使用 `output/report.css` 样式。
3. `qa_check.json` — QA 结果，至少包含 `checks_passed`、`issues`、`checked_at`。结构由 `src/common/snapshot_validator.py` 定义。
4. `references.json` — 引用与数据来源列表。

## 输出 Schema 映射

Skill 生成的中间 JSON 必须包含以下 13 个 section，由 Python adapter 映射到 `ResearchSnapshot`：

| Section | ResearchSnapshot Field | Required |
|---------|------------------------|----------|
| I. Metadata | `research_metadata` | Yes |
| II. Core Narrative | `core_narrative` | Yes |
| III. Six-Dimension Analysis | `six_dimensions` (list of typed dimensions) | Yes |
| IV. Investment Logic | `investment_logic` | Yes |
| V. Investment Thesis Table | `investment_thesis_table` | Yes |
| VI. Company Overview | `company_overview` | Yes |
| VII. Financial Data | `financial_data` | Yes |
| VIII. Valuation Data | `valuation` / `valuation_data` | Yes |
| IX. Catalyst Calendar | `catalyst_calendar` | Yes |
| X. Scenario Analysis | `scenario_analysis` | Yes |
| XI. Risk List | `risks` / `risks_typed` | Yes |
| XII. Industry & Supply Chain | `industry_supply_chain` | Yes |
| XIII. Stock Price & Trading Data | `stock_price_data` | Yes |

### JSON 字段约定

- 所有日期使用 ISO 格式字符串（`YYYY-MM-DD`）。
- 所有金额/价格使用 number，Python 端会转换为 `Decimal` 或 `float`。
- `six_dimensions` 必须是一个 list，每项包含 `dimension_id`（H1-H6）、`dimension_name`、`conclusion`、`key_data_support`、`so_what`。
- `risks_typed` 是一个 list，每项包含 `risk_type`、`description`、`impact`、`probability`。
- `scenario_analysis` 必须包含 `optimistic`、`base_case`、`pessimistic`，且概率之和约等于 1。
- `catalyst_calendar` 至少包含 4 个事件，其中至少 2 个 `importance` 为 `High`，且必须包含下次财报事件。

## 验证

生成后，Python worker 会运行 `src/common/snapshot_validator.py` 对 `snapshot.json` 进行结构预检。
未通过校验的报告会被记录问题列表，但不会阻止文件落盘（由用户后续决定是否重跑）。

## 当前阶段

Slice 5b 已完成：
- 目录结构与输出约定跑通。
- `ResearchSnapshot` schema 已覆盖 equity-researcher 全部 13 个 section。
- 三级缓存（non-existent / stale / minor refresh）在 Python worker 中实现。
- 研报内容在 `--mock` 模式或 Kimi CLI 不可用时使用 fixture 数据，保证 CI 与离线环境可测试。

后续扩展：
- 在 `scripts/` 增加图表生成与 HTML report validator。
- 接入真实行情/公告数据源，替换缓存中的 stub 事件检测。
