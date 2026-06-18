# Climbing — 产品需求文档（PRD）

> 版本：0.2.0  
> 状态：ready-for-agent  
> 基于 grilling + domain modeling 会话整理，与 `CONTEXT.md`、5 份 ADR 保持一致。

---

## Problem Statement

个人 A 股投资者在研究与持仓跟踪中面临以下问题：

1. **研究结论散落在各处**：财报、公告、行情、卖方观点、宏观数据分散在不同终端和聊天记录中，难以形成可追溯的档案。
2. **研究与交易计划脱节**：看了研报之后没有结构化地把假设、目标价、失效条件写下来，导致后续很难判断“当初为什么买/卖”。
3. **持仓与计划无法联动核对**：真实持仓来自券商流水，交易计划来自研究结论，两者通常分开管理，无法自动检查偏离。
4. **每日复盘负担重**：收盘后需要手动汇总市场、持仓、计划、新闻，既耗时又容易遗漏关键变化。
5. **证据链不完整**：当判断出错时，难以回溯当时用了什么数据、做了什么假设、 confidence 是多少。

Climbing 要解决的是**把“研究结论、证据、计划、偏离、复盘”组织成可追溯的工作流**，而不是替用户做交易决策。

---

## Solution

构建一个**本地优先、agent 驱动、快照化**的 A 股个人投研研究与持仓跟踪系统：

- **自然语言入口**：用户通过对话或 Web 按钮触发任务（如“分析 000725”“收盘巡检”“复核交易计划”）。
- **Agent 负责分析与判断**：研报生成、交易计划草案、每日复盘、计划复核、宏观月报解释由 agent 完成。
- **Python 负责确定性工作流**：数据采集、标准化、版本化、快照生成、校验、触发器检查由 Python 完成。
- **快照作为核心抽象**：所有事实与分析产物都以结构化 snapshot 形式落盘，形成可追溯的证据链。
- **真实交易必须手动录入**：系统不做自动下单、不做自动修改持仓，持仓变更只能来自用户导入或录入的交易流水。

---

## User Stories

### 个股研究与研报

1. As a 用户，我想要输入股票代码就生成一份深度研报，so that 我可以快速建立对一只股票的系统认知。
2. As a 用户，我想要研报中每个结论都附带假设、证据和失效条件，so that 我能判断结论是否仍然成立。
3. As a 用户，我想要研报自动输出 PDF 和结构化 ResearchSnapshot，so that 后续交易计划可以直接引用研究版本。
4. As a 用户，我想要系统在我研究的股票出现财报、重大公告、监管处罚等事件时提示我重跑研究，so that 我不会基于过期结论做决策。
5. As a 用户，我想要仅在市场价格/估值变化时先生成轻量“数据刷新”快照，so that 不必每次都跑完整深度研报。
6. As a 用户，我想要研报数据来源明确标注权威层级，so that 当不同来源冲突时我知道该以谁为准。
7. As a 用户，我想要研报的六维分析、估值、风险以统一 schema 输出，so that 不同股票的结论可以横向比较。

### 持仓管理

8. As a 用户，我想要从券商/同花顺导出的 CSV 导入交易流水，so that 系统能自动重建我的持仓。
9. As a 用户，我想要持仓由交易流水按 FIFO 推导，而不是独立导入持仓快照，so that 收益计算与流水可互相校验。
10. As a 用户，我想要系统每日收盘后自动刷新持仓市值、浮动盈亏、已实现收益，so that 我总览账户状态。
11. As a 用户，我想要看到资金加权收益率（Modified Dietz）和时间加权收益率（TWRR），so that 我能剔除出入金影响衡量投资能力。
12. As a 用户，我想要看到仓位结构、行业/板块暴露、集中度、回撤、波动率，so that 我清楚组合风险。
13. As a 用户，我想要证券代码在导入时自动标准化（A 股、ETF、可转债），so that 不同来源的数据能正确对齐。
14. As a 用户，我想要手动补录当日交易流水，so that 即使券商文件还没导出也能保持持仓最新。

### 交易计划

15. As a 用户，我想要基于个股 ResearchSnapshot、MarketSnapshot、PortfolioSnapshot 和 DailyReviewSnapshot 生成交易计划草案，so that 计划有完整证据链。
16. As a 用户，我想要交易计划包含方向、目标价区间、分批策略、仓位上限、风险预算、失效条件、替代情景、触发器和复盘频率，so that 计划足够结构化。
17. As a 用户，我想要系统在价格触发、趋势逆转、财报 miss、公告改变逻辑、仓位越界时提示计划偏离，so that 我不会错过需要复核的时机。
18. As a 用户，我想要所有计划变更都必须由我手动确认并形成新的 plan_version，so that 系统不会自动篡改我的计划。
19. As a 用户，我想要计划与真实持仓弱联动：执行后手动补入流水，系统再关联到对应计划版本，so that 保持“计划只提醒、不自动交易”的边界。
20. As a 用户，我想要系统自动计算计划收益率、执行偏差、是否按计划执行、买卖点是否符合原假设，so that 复盘时有量化依据。
21. As a 用户，我想要在板块热度、市场情绪、仓位风险变化时发起计划复核，so that 计划能随环境更新。

### 每日收盘更新与复盘

22. As a 用户，我想要说“收盘更新”或“复盘今天”就触发完整流程，so that 我不需要手动执行多个脚本。
23. As a 用户，我想要系统先生成 MarketSnapshot（市场事实），再生成 PortfolioSnapshot（账户事实），最后由 agent 生成 DailyReviewSnapshot（复盘分析），so that 事实与分析边界清晰。
24. As a 用户，我想要 DailyReviewSnapshot 包含今日要点、市场情绪判断、持仓风险、计划偏离、需要复核的股票、明日关注清单，so that 我快速抓住重点。
25. As a 用户，我想要一键巡检（说“climbing”或点击 Web“今日巡检”）后，系统只提示需要复核的股票、偏离的计划、过期的数据，而不自动生成研报或修改计划，so that 我不会被未经确认的操作打扰。
26. As a 用户，我想要 Python worker 在收盘更新中处理数据固化、去重、校验、版本化，而不做市场判断，so that 结果是可审计的。

### 宏观月报

27. As a 用户，我想要每月初看到“资金面四问”叙事月报：M2 是否扩张、政策是否引导、居民是否搬家、无风险利率是否下行，so that 我对宏观环境有统一框架。
28. As a 用户，我想要月报底层数据按增长、通胀、流动性、市场结构四类归集，so that 叙事有事实支撑。
29. As a 用户，我想要 Python 负责从同花顺/央行等来源拉取宏观事实并写入标准化表，agent 负责把事实解释为“资金面四问”，so that 事实与解释分离。
30. As a 用户，我想要月报输出标签（过热/中性/偏冷）附带证据链，so that 我能追溯标签是怎么来的。

### 系统入口与交互

31. As a 用户，我想要通过自然语言对话触发所有任务，so that 交互更自然。
32. As a 用户，我想要通过 Web 前端查看 Dashboard、个股分析、持仓、计划、宏观月报，so that 我有图形化入口。
33. As a 用户，我想要 Python CLI 只作为 agent 背后的 worker，不直接作为用户入口，so that 我不会误操作底层命令。
34. As a 用户，我想要风险约束采用软性提醒（满仓、集中持仓、现金不足、计划与持仓冲突），so that 系统不会硬性拦截我的操作。

### 数据与可审计性

35. As a 用户，我想要所有标准化表和 snapshot 都包含 `source`、`retrieved_at`、`version` 字段，so that 我能追溯数据来源和时间。
36. As a 用户，我想要多源数据冲突时以权威层级（官方披露 > 同花顺/iFinD > agent 聚合数据）为准并记录差异，so that 口径混乱时可仲裁。
37. As a 用户，我想要持仓数据本地存储、不对外传输，so that 我的账户信息安全。
38. As a 用户，我想要报告快照保留最近 N 份并支持版本回溯，so that 我能查看历史判断。

---

## Implementation Decisions

### 1. 职责边界：Agent vs Python vs Web

- **Agent**：自然语言理解、skill 编排、分析判断、研报生成、计划草案、复盘解读、宏观叙事。
- **Python**：数据库/文件读写、数据采集与标准化、快照生成、版本化、校验、触发器检测、工作流执行。
- **Web**：展示 snapshot、接收用户确认、提供按钮触发 agent 任务。
- **真实交易与持仓变更**：只能来自用户手动录入或导入的交易流水。

### 2. 快照体系作为核心抽象

所有产物分为两类：

- **事实 snapshot（Python 生成）**：
  - `MarketSnapshot`：指数涨跌、成交额、市场宽度、涨跌家数、板块热度、资金流、两融、ETF/北向资金、情绪评分。
  - `PortfolioSnapshot`：持仓明细、现金、总资产、总市值、浮动盈亏、已实现收益、仓位比例、行业/板块暴露、回撤、计划关联状态。
- **分析 snapshot（Agent 生成）**：
  - `ResearchSnapshot`：个股深度研报结构化输出 + PDF 研报。
  - `DailyReviewSnapshot`：每日复盘分析。
  - `TradePlan`：交易计划（结构化对象，带版本）。
  - `PlanReviewSnapshot`：计划复核记录。
  - 宏观月报：agent 基于 `capital-flow` 事实表生成的“资金面四问”叙事。

每个 snapshot 必须包含 `source`、`retrieved_at`、`version`、`data_cutoff` 等元数据。

### 3. Skill 目录结构

统一收敛到 `skills/` 目录，按 Climbing 上下文拆分：

- `skills/stock-research/`：个股深度研报（改写自 `equity-researcher/`，只保留 Equity Report 深度模式，输出 PDF + ResearchSnapshot）。
- `skills/data-refresh/`：数据刷新与快照生成（被 agent 调用以触发 Python worker）。
- `skills/daily-review/`：每日复盘（消费 MarketSnapshot + PortfolioSnapshot + 触发器结果）。
- `skills/trade-plan/`：交易计划生成（基于完整上下文输出草案）。
- `skills/plan-review/`：交易计划复核（在偏离或环境变化时发起）。
- `skills/capital-flow/`：宏观月报资金面解释（基于 Python 生成的事实表输出叙事）。

原 `equity-researcher/` 不直接复用，而是作为方法论参考拆分为适配版本。

### 4. 个股研究引擎

- 不在 Python 端重写六维分析、估值或报告生成逻辑。
- 由 `skills/stock-research/` 作为深度研究引擎，输出 PDF 研报 + 结构化 `ResearchSnapshot`。
- Climbing Python 端负责：缓存判断（不存在 / stale / 仅价格变化）、job 管理、Kimi CLI 调度、产物校验、版本追溯、交易计划引用。
- 产物目录：`data/reports/equity/{ticker}/{version}/`，必须包含 `snapshot.json`（完成标记）、`report.pdf`、`qa_check.json`、`references.json`。

### 5. 交易计划状态机与版本化

- 计划状态：草稿 → 激活 → 部分触发 → 完全触发 → 假设被破坏 → 关闭 → 复盘完成。
- 所有状态迁移必须用户确认，并形成新的 `plan_version`。
- Python 端负责状态机持久化、触发器检测、版本对比、审计日志、复盘字段计算。
- 计划与真实持仓弱联动：执行后用户手动补入流水，系统再把流水关联到对应计划版本。

### 6. 持仓与交易流水

- 交易流水是持仓的唯一真相源。
- 持仓按 FIFO 推导，不是独立导入的快照。
- 证券代码标准化在 `data_standardization/` 中完成，覆盖 A 股主板/创业板/科创板/北交所、ETF、可转债；无法自动识别时弹出人工确认。
- 收益计算三层口径：当前持仓市值与浮动盈亏、已实现收益、资金加权收益率 / 时间加权收益率。

### 7. 数据层与存储

- 本地优先，默认落盘到 `data/` 目录。
- 标准化表使用 Parquet 或 JSON 文件，包含 `source`、`retrieved_at`、`version` 字段。
- 报告快照路径：`data/reports/{report_type}/{ticker?}/{version}.md` 或按目录组织。
- 版本格式：`YYYYMMDDhhmmss-{hash_prefix}`。

### 8. 数据源权威层级

- **Tier 1**：官方披露（央行、交易所、财政部、公司财报/公告）。
- **Tier 2**：同花顺 / iFinD 等专业数据终端。
- **Tier 3**：Agent 聚合数据（kimi-datasource / akshare / tushare / yfinance 等）。
- 冲突时以更高权威来源为准，并记录差异。
- 个股研究以 kimi-datasource 为主，缺失时允许 agent 通过 akshare/tushare 补充并显式标注 `source` 和 `confidence`。
- 持仓交易坚持券商/同花顺导出文件导入，不走 API 自动同步。
- MarketSnapshot 日度数据优先使用 kimi-datasource，不足时用 akshare/tushare 补充。
- 宏观月报资金面由 Python 取数/标准化模块输出事实表，agent 负责解释。

### 9. 触发器与复核

- 触发器类型（第一版）：价格、时间、事件、市场情绪、仓位风险。技术指标仅作为辅助证据。
- ResearchSnapshot  freshness 三层规则：不存在 → 必须跑完整研报；存在但过期或遇到事件 → stale 重跑；仅价格/估值变化 → 先生成 minor 数据刷新。
- 每日收盘流程：更新市场数据 → MarketSnapshot → 刷新持仓 → PortfolioSnapshot → 检查计划触发器与 stale ResearchSnapshot → 生成复核 job → agent 生成 DailyReviewSnapshot。

### 10. 风险约束

- 软性提醒，不硬性拦截。
- 提醒场景：满仓、集中持仓、行业过度暴露、现金不足、计划与持仓冲突。
- 最终由用户确认。

### 11. 前端

- React + TypeScript + Vite + Recharts + Zustand。
- 页面：Dashboard、个股分析、持仓管理、交易计划、宏观月报、巡检/复核中心。
- Web 通过读取本地 snapshot 文件或调用后端接口展示；核心确认操作通过自然语言或按钮触发 agent。

### 12. 复用现有代码

- 保留 `src/common/config.py`、`src/common/paths.py`、`src/common/logger.py` 的约定。
- 保留 `src/data_standardization/versioner.py` 的版本化逻辑。
- 保留 `src/analysis/stock_scorer.py`、`src/analysis/market_temperature.py`、`src/analysis/plan_deviation.py` 的评分器接口，逐步替换占位实现。
- 保留 `src/report_generation/` 的 Jinja2 模板机制，扩展为 snapshot 渲染。
- 改写 `src/cli/` 命令为 agent worker 命令，补充必要参数和错误处理。

---

## Testing Decisions

### 测试 seam

以 **“Python CLI worker → snapshot 文件”** 作为唯一集成测试 seam：

```
natural language intent
       ↓
   agent scheduling
       ↓
Python CLI command
       ↓
snapshot file(s) on disk
       ↓
schema validation + downstream rendering
```

所有功能（个股研究、数据刷新、每日更新、持仓刷新、计划复核）都通过验证其生成的 snapshot 文件来测试。

### 好测试的标准

- **只测外部行为，不测实现细节**：验证命令执行后是否生成了符合 schema 的 snapshot 文件，而不是验证内部调用了哪个函数。
- **用 fixture 替代真实外部数据**：测试中使用本地 fixture 数据，避免依赖 kimi-datasource、akshare、同花顺等外部 API。
- **schema 优先**：每个 snapshot 必须有对应的 Pydantic schema，测试首先验证 schema 合规。
- **下游可消费性**：验证生成的 snapshot 能被下游模板或 agent skill 正确读取和渲染。

### 需要测试的模块

- `src/cli/` 所有命令的集成测试：
  - `update daily` 生成 MarketSnapshot、PortfolioSnapshot。
  - `analyze stock` 调用 `skills/stock-research/` 后生成 ResearchSnapshot（可用 mock skill 输出）。
  - `plan create` / `plan check` 生成 TradePlan 和 PlanReviewSnapshot。
  - `portfolio import-transactions` 后生成 PortfolioSnapshot。
- `src/data_standardization/` 的单元测试：证券代码标准化、交易流水去重、FIFO 持仓计算。
- `src/analysis/` 的单元测试：评分器、市场温度、计划偏离、收益计算。
- `src/report_generation/` 的模板渲染测试：给定 snapshot 能渲染为 Markdown。
- `src/common/models.py` 的 schema 校验测试。

### 先验测试

- 现有 `tests/test_analysis.py` 已覆盖技术指标和个股评分器，作为分析引擎测试的基线。
- 现有 `tests/test_common.py` 可作为配置和路径测试的参考。

---

## Out of Scope

1. **自动交易执行 / 自动下单**：系统不接入券商交易 API，不自动修改持仓。
2. **实时行情与盘中微观结构博弈**：第一版以日更和事件驱动为主，不做 tick 级数据。
3. **多用户 / SaaS 化**：系统为单用户本地使用设计。
4. **移动端 App**：第一版只有 Web 前端和对话入口。
5. **投顾服务 / 向第三方提供投资建议**：仅作为个人研究工具。
6. **完整回测引擎**：计划复盘会计算执行偏差，但不提供通用策略回测。
7. **ESG / 专利 / 企业关系图谱**：列为 P2 外部数据增强版，不在本地研究 MVP 中实现。
8. **Excel 财务模型交互编辑**：L2 深度研报的 Excel 模型由 agent skill 生成，Python 端不维护可编辑模型。
9. **受限制数据再分发**：Yahoo Finance、同花顺等受协议限制的数据仅本地使用，不得作为权威口径再分发。

---

## Further Notes

1. **资金量假设**：用户资金量约为 10–15 万人民币，风险约束采用软性提醒与此规模匹配。
2. **离线能力**：Python worker 和已生成 snapshot 的读取可在离线环境运行；生成新研究、新复盘需要 agent 运行时和外部数据源。
3. **数据库选型待决**：当前使用 Parquet/JSON 文件存储，后续如果数据量或查询复杂度增长，可迁移到 SQLite 或 DuckDB，但应保持 schema 和 CLI 接口不变。
4. **Web 状态管理待决**：前端状态管理方案（Zustand 或其他）可在实现阶段细化，但页面路由和核心视图已在 `docs/architecture.md` 中定义。
5. **Skill schema 待细化**：每个 skill 的输入/输出 schema 需在 `skills/*/README.md` 或 `src/common/models.py` 中进一步定义。
6. **人确认边界**：录入交易流水、生成/更新 ResearchSnapshot、激活交易计划、修改计划版本，必须由用户唤醒和确认。
7. **与 `equity-researcher/` 的关系**：`equity-researcher/` 作为方法论资产保留参考，Climbing 使用拆分后的 `skills/stock-research/`，并强制其输出符合 Climbing snapshot schema。
8. **月报触发**：宏观数据发布通常有固定日历，月报任务可在每月第 3 个工作日运行，或在主要数据（M2、社融、CPI/PPI）发布后由 agent 主动触发。
9. **版本化约定**：所有 snapshot 和标准化表使用 `version` 字段；报告快照文件系统路径也包含版本标识，便于回溯。
10. **文档联动**：本 PRD 与 `CONTEXT.md`（领域术语表）、`docs/architecture.md`（技术架构）、`docs/adr/`（架构决策记录）共同构成实现依据。

---

## 验收标准

- 收盘后一键更新成功率高且可重跑。
- 任一持仓的收益、累计收益和交易流水可互相校验。
- 任一交易计划可追溯到对应研究报告版本。
- 任一告警/偏离可展开到具体触发条件和证据。
- 月报在主要宏观数据发布后一个工作日内自动出稿。
- 受限制数据源不得作为权威口径再分发。
- 所有新增 snapshot 必须通过 Pydantic schema 校验。
- CLI worker 命令必须能被 agent 通过自然语言调度，且返回结构化结果。
