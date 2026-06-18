# Handoff: Climbing 投研系统 —  grilling 完成，待进入下一步

## 会话目标

用户希望构建一个 A 股个人投研研究与持仓跟踪系统（项目代号 Climbing）。本次会话使用 `/grill-with-docs` + `/domain-modeling` 对核心领域模型、系统边界、数据源、工作流和人与 agent 的分工进行了逐层澄清。

## 已完成的工作

### 1. 领域模型澄清（已写入 CONTEXT.md）

- 个股全景分析：`skills/stock-research/` 作为深度研究引擎，输出 `ResearchSnapshot` + PDF 研报
- 交易计划：由 agent 基于完整上下文生成草案，用户确认后激活
- 持仓管理：交易流水为唯一真相源，生成 `PortfolioSnapshot`
- 每日收盘更新：`MarketSnapshot` → `PortfolioSnapshot` → 触发器检查 → agent 生成 `DailyReviewSnapshot`
- 宏观月报：「资金面四问」作为叙事层，底层复用 PRD 指标分类
- 数据源边界与权威层级
- 系统入口：自然语言 + Web 为主，CLI 只作 agent worker
- 风险约束：软性提醒，不硬性拦截

### 2. 已创建的架构决策记录（ADR）

- `docs/adr/0001-equity-researcher-as-research-engine.md`
- `docs/adr/0002-trade-plan-agent-driven.md`
- `docs/adr/0003-agent-first-daily-workflow.md`
- `docs/adr/0004-data-source-hierarchy.md`
- `docs/adr/0005-system-entry-and-human-agent-boundary.md`

### 3. 已探索的代码库

- `docs/prd.md` — 产品需求文档
- `docs/architecture.md` — 技术架构
- `capital_flow.py` — 待改造为资金面取数 + 标准化模块
- `data/近一年资金明细.xls` — 交易流水账本（实际为 GBK 编码的 TSV），用作持仓初始化数据
- `config/tickers.yaml` — 观察列表
- `config/scoring_rules.yaml` — 评分规则
- `equity-researcher/` — 独立的研报 skill，待拆分为 `skills/` 下的适配版本

## 关键结论（不重复细节，详见 CONTEXT.md 与 ADR）

1. **不做自动交易**：真实持仓变更只能来自用户手动录入交易流水。
2. **agent 负责分析判断，Python 负责确定性工作流**：研报生成、每日复盘、计划复核走 agent；数据固化、快照生成、版本校验走 Python。
3. **快照体系是核心抽象**：`ResearchSnapshot`、`MarketSnapshot`、`PortfolioSnapshot`、`DailyReviewSnapshot` 构成事实层与分析层的边界。
4. **Skill 统一收敛到 `skills/` 目录**：建议拆分为 `stock-research/`、`data-refresh/`、`daily-review/`、`trade-plan/`、`plan-review/`、`capital-flow/`。
5. **数据源分层**：官方披露 > 同花顺/iFinD > agent 聚合数据。

## 用户未明确但下一步可能需要决定的事项

- 具体数据库选型（SQLite / DuckDB / Parquet 文件）
- Web 前端页面结构与状态管理方案
- 每个 skill 的输入/输出 schema 细节
- `ResearchSnapshot`、`MarketSnapshot`、`PortfolioSnapshot`、`TradePlan` 的 Pydantic schema
- 用户资金量：10-15 万人民币（来自会话，无敏感信息）

## 建议下一步

根据 ask-matt 的主流程，下一步通常是：

1. `/to-prd`：把 grilling 结果整理成正式 PRD（覆盖范围、验收标准、阶段拆分）
2. `/to-issues`：把 PRD 拆成可独立实现的 issue
3. `/implement`：逐个 issue 实现，每个 issue 开一个新会话

如果上下文窗口允许，也可以直接在当前会话 `/to-prd`。

## 建议下一个 agent 调用的 skills

- `/to-prd` — 将本次 grilling 整理为 PRD
- `/domain-modeling` — 继续细化具体 schema
- `/codebase-design` — 设计 skill 接口、数据层和模块边界
- `/tdd` — 如果下一步进入实现，建议测试先行
- `skills/equity-researcher/` 的现有文件 — 作为拆分 `skills/stock-research/` 的参考

## 注意事项

- 不要直接手动执行 `python -m src.cli.main ...` 作为用户入口；CLI 只应被 agent 调用。
- 不要重写 `equity-researcher` 的分析逻辑；应拆分为适配 Climbing 的 skills。
- 持仓数据来自用户提供的交易流水文件，涉及个人账户信息，后续处理时注意本地化存储、不对外传输。

---
