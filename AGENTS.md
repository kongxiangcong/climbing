# Climbing — AI 助手开发规范

## 项目概述

这是一个**本地优先、批处理优先**的 A 股个人投研研究与持仓跟踪系统。系统边界限定在研究、持仓跟踪、计划管理、报告生成，**不做交易执行、不做自动下单、不做盘中微观结构博弈**。

## 核心约定

### 1. 数据来源约定

- **权威层优先**：财报、公告、股东变动等以官方披露为准，新闻和二手解读仅作补充证据
- **来源可追溯**：所有标准化数据必须保留 `source`、`retrieved_at`、`version` 字段
- **授权合规**：Yahoo Finance 等受限制数据源不得作为权威主数据再分发

### 2. 代码风格

- Python 3.10+，使用类型注解
- 函数职责单一，优先纯函数，便于测试
- 配置统一从 `config/settings.yaml` 加载，禁止硬编码路径
- 日志使用 `src.common.logger.get_logger(__name__)`

### 3. 模块边界

| 模块 | 职责 |
|------|------|
| `data_ingestion` | 只负责从外部源拉取原始数据，不做业务判断 |
| `data_standardization` | 清洗、对齐、版本化，输出中间层视图 |
| `analysis` | 基于中间层计算指标和评分，不直接读原始 API 数据 |
| `report_generation` | 读取分析结果，生成 Markdown/HTML 报告快照 |
| `cli` | 命令行入口，编排上述模块 |

### 4. 报告文案约定

- 禁止出现“建议立刻买入”“短期必涨”“胜率 90%”等荐股语义
- 统一使用“当前假设”“关键催化”“失效条件”“乐观/中性/悲观情景”“估值区间”“计划动作建议”
- 每个结论必须附带证据链接或数据来源

### 5. 数据目录约定

```
data/
├── raw/              # API 原始返回，按日期或数据源分目录
├── standardized/     # 清洗对齐后的 Parquet/CSV
├── features/         # 特征计算结果
├── reports/          # 生成的报告快照
└── user/             # 用户持仓、交易流水、交易计划（用户手动维护）
```

### 6. 前端约定

- React + TypeScript + Vite
- 页面：Dashboard、StockAnalysis、Portfolio、Plans、MacroReport
- 组件职责单一，状态管理使用 React Context 或 Zustand
- 图表使用 ECharts 或 Recharts

## 常用命令

```bash
# 收盘后一键更新
python -m src.cli.main update daily

# 生成个股分析报告
python -m src.cli.main analyze 000725.SZ

# 查看持仓状态
python -m src.cli.main portfolio summary

# 启动前端
cd web && npm run dev
```

## 注意事项

- 修改配置时同步更新 `config/settings.yaml` 和 `pyproject.toml`（如新增依赖）
- 新增数据源时先在 `data_ingestion/` 添加客户端，并在 `data_standardization/` 中添加标准化逻辑
- 所有分析模型输出使用 Pydantic 模型约束字段

## Agent skills

### Issue tracker

Issues and PRDs live as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles use their default names: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo: read `CONTEXT.md` at the repo root and `docs/adr/` for architectural decisions. See `docs/agents/domain.md`.
