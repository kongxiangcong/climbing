# Climbing — 领域术语表

> 本文件记录项目内各上下文统一使用的业务术语，不含实现细节。

## 个股全景分析

- **研究引擎**：由 `skills/equity-researcher/` 提供深度研报能力，Climbing 不在 Python 端重写六维分析、估值或报告生成逻辑。
- **数据边界**：个股研究所需研报、财报、行情、公告等数据由 Kimi agent 通过 `kimi-datasource` skill 获取；Climbing Python 代码不直接调用同花顺/东方财富等外部 API。
- **产物形态**：每次分析生成 PDF 深度研报 + 符合 Climbing schema 的结构化研究文档（ResearchSnapshot）。
- **ResearchSnapshot**：个股研究的标准化快照，必须包含 `source`、`retrieved_at`、`version`、`data_cutoff`、`report_version` 等字段，写入 `data/reports/`、`data/standardized/`、`data/features/`。
- **可复用研究结论**：判断是否唤醒 agent 的三层规则：
  1. 不存在 ResearchSnapshot → 必须跑完整深度研报；
  2. Snapshot 存在，但 `data_cutoff` / `retrieved_at` 超过默认有效期（如 7 天），或遇到财报、业绩预告、重大公告、监管处罚、股权激励、分红方案、行业政策等事件 → 标记为 `stale`，触发完整重跑；
  3. 无基本面事件，仅股价、估值、成交、持仓状态变化 → 先生成轻量「数据刷新 / 价格复核」minor 版本，只在结论实质变化时升级为 major 重跑。
- **产物目录**：`data/reports/equity/{ticker}/{version}/`，必须包含 `snapshot.json`（完成标记）、`report.pdf`、`qa_check.json`、`references.json`。
- **调度职责**：Climbing Python 端负责 job 管理、本地缓存检查、Kimi CLI/agent 唤醒、产物校验、版本追溯、交易计划引用。

## 宏观月报

- **资金面四问（叙事层）**：面向使用者的四个宏观判断问题
  - M2 是否扩张？——货币总量有没有水
  - 政策是否引导？——监管层是否主动引导资金入市
  - 居民是否搬家？——居民资产配置是否从存款/理财向权益迁移
  - 无风险利率是否下行？——股票相对债券的性价比是否提升

- **宏观指标分类（数据层）**：底层数据按四类归集
  - **增长**：PMI、工业增加值、社会消费品零售总额、固定资产投资
  - **通胀**：CPI、PPI
  - **流动性**：M2、M1、社融、贷款、利率（含无风险利率）
  - **市场结构**：成交额、换手率、融资融券余额、估值、ETF/基金资金流

- **资金面评分模块**：`capital_flow.py` 升级后的职责，用于从同花顺等来源自动取数、打分，并生成填充「资金面四问」的证据，不再作为月报顶层术语对外呈现。

## 持仓管理

- **交易流水（Transaction Ledger）**：持仓的唯一真相源。来自券商导出的 CSV / 同花顺资金明细，也支持手动录入当日操作。
- **持仓（Position）**：由交易流水按 FIFO 推导得出，不是独立导入的快照。
- **证券代码标准化**：在 `data_standardization/` 中完成，规则覆盖 A 股主板/创业板/科创板/北交所、ETF、可转债；无法自动识别时弹出人工确认。
- **收益计算三层口径**：
  1. **当前持仓市值与浮动盈亏**：每日收盘刷新；
  2. **已实现收益**：按 FIFO 从交易流水计算；
  3. **资金加权收益率（Modified Dietz）/ 时间加权收益率（TWRR）**：衡量投资能力，剔除出入金影响。
- **数据导入方式**：券商 CSV 增量追加 + 手动录入当日操作。

## 交易计划

- **计划生成主体**：由 agent 基于完整上下文生成计划草案，Climbing Python 端不自动生成交易策略。
- **计划输入上下文**：必须包括 个股 ResearchSnapshot、大盘 MarketSnapshot、每日复盘 DailyReviewSnapshot、板块资金流向、市场成交量/资金量、板块热度、个人 PortfolioSnapshot（当前持仓、现金余额、已有仓位、历史流水）和风险约束。
- **计划方向**：建仓、加仓、减仓、清仓、观察/等待。已有持仓股票默认进入持仓相关计划；未持仓股票默认进入观察或建仓计划。
- **触发器（第一版）**：价格、时间、事件、市场情绪、仓位风险。技术指标仅作为辅助证据，不单独驱动交易。
- **优化调整**：由 agent 在每日复盘、股价偏离、财报公告、板块热度变化、市场情绪变化、仓位风险变化时发起「计划复核」，输出多空讨论、基本面复核、估值复核、市场环境复核和计划变更建议；所有变更必须用户手动确认并形成新的 `plan_version`。
- **与真实持仓联动**：弱联动。计划只提醒，不自动交易，不自动篡改持仓；用户执行后手动补入成交流水，系统再把流水关联到对应计划版本。
- **复盘字段**：除文本复盘外，自动计算计划收益率、执行偏差、是否按计划执行、买卖点是否符合原假设、计划成功/失败原因。

## 每日收盘更新与快照体系

- **Daily Update Workflow**：由 agent 理解用户意图并调度，Python 作为确定性 worker 执行。用户通过自然语言（如「收盘更新」「复盘今天」）触发。
- **MarketSnapshot**：每日市场状态事实快照，输入到宏观月报和交易计划。字段包括指数涨跌、成交额、市场宽度、涨跌家数、板块热度、资金流入流出、两融、ETF/北向资金、情绪评分等。
- **PortfolioSnapshot**：每日收盘后个人账户事实快照，由 Python 基于本地流水和价格数据确定性生成。字段包括持仓明细、现金、总资产、总市值、浮动盈亏、已实现收益、仓位比例、行业/板块暴露、回撤、计划关联状态等。
- **DailyReviewSnapshot**：agent 基于 PortfolioSnapshot、MarketSnapshot、计划触发器、公告新闻、板块变化生成的每日复盘分析。内容包括今日要点、市场情绪判断、持仓风险、计划偏离、需要复核的股票、明日关注清单。
- **执行顺序**：
  1. 更新市场与价格数据 → 生成 MarketSnapshot；
  2. 刷新持仓市值和收益 → 生成 PortfolioSnapshot；
  3. 检查交易计划触发器和 ResearchSnapshot stale 状态 → 生成复核 job；
  4. agent 读取结构化快照 → 生成 DailyReviewSnapshot。
- **事实 vs 分析边界**：MarketSnapshot 和 PortfolioSnapshot 是事实输入；DailyReviewSnapshot、ResearchSnapshot、宏观月报解释是分析输出。Python 负责数据固化、去重、校验、版本化，不做市场判断。

## 数据源与权威层级

- **个股研究数据**：kimi-datasource 为主；缺失时允许 agent 通过 akshare / tushare 等 API 补充，必须显式标注 `source` 和 `confidence`。
- **持仓交易数据**：坚持券商/同花顺导出文件导入，不走 API 自动同步。
- **MarketSnapshot 日度数据**：优先 kimi-datasource 日度行情/资金接口；不支持板块资金流等字段时，用 akshare / tushare 等 API 补充。
- **宏观月报资金面**：`capital_flow.py` 改造为 Python 取数 + 标准化模块，输出宏观事实表；agent skill 负责把事实解释为「资金面四问」。
- **权威层级**：官方披露（央行、交易所、财政部等）> 同花顺 / iFinD 等专业数据终端 > agent 聚合数据（含 kimi-datasource / akshare / tushare）。冲突时以更高权威来源为准，并记录差异。

## 系统入口与技能边界

- **用户入口**：自然语言对话 + Web 前端为主；Python CLI 只作为 agent 背后的确定性 worker，不直接面向用户。
- **典型入口**：「分析 000725」「收盘巡检」「复核交易计划」「生成月报」等自然语言指令，或 Web 上的对应按钮。
- **一键巡检**：用户说「climbing」或点击 Web「今日巡检」触发。agent 调度 Python worker 更新行情、市场、板块、持仓市值和计划触发状态，生成 MarketSnapshot、PortfolioSnapshot 和快速 DailyReviewSnapshot；巡检结束后只提示需要复核的股票、偏离的计划、过期的数据，不自动生成 ResearchSnapshot 或修改交易计划。
- **Skill 目录**：统一放在 `skills/` 下，按 Climbing 上下文拆分，不建议原封不动复用独立 equity-researcher。建议目录：
  - `skills/stock-research/`：个股深度研报
  - `skills/data-refresh/`：数据刷新与快照生成
  - `skills/daily-review/`：每日复盘
  - `skills/trade-plan/`：交易计划生成
  - `skills/plan-review/`：交易计划复核
  - `skills/capital-flow/`：宏观月报资金面解释
- **风险约束**：软性提醒，不硬性拦截。系统提示满仓、集中持仓、行业过度暴露、现金不足、计划与持仓冲突等事实，最终由用户确认。
- **人工确认边界**：录入交易流水、生成/更新 ResearchSnapshot、激活交易计划、修改计划版本，必须由用户唤醒和确认。
- **最终职责边界**：
  - **agent**：自然语言交互、分析判断、skill 编排；
  - **Python**：数据库、快照、版本、校验、工作流执行；
  - **Web**：展示与确认；
  - **真实交易与持仓变更**：只能来自用户手动录入流水。

---
