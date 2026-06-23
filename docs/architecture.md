# Climbing — 技术架构

## 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Web 前端                              │
│   React + TypeScript + Vite + Recharts + Zustand            │
│   Dashboard | 个股分析 | 持仓 | 计划 | 宏观月报             │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / 静态报告
┌───────────────────────▼─────────────────────────────────────┐
│                      Python 后端                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  data_ingestion │  data_standardization │  analysis   │   │
│  │  数据采集    │  │  数据标准化   │  │  分析引擎        │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            report_generation 报告生成                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   CLI 命令行入口                        │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │ 文件系统
┌───────────────────────▼─────────────────────────────────────┐
│                         数据层                               │
│   data/raw/ | data/standardized/ | data/features/            │
│   data/reports/ | data/user/                                 │
└─────────────────────────────────────────────────────────────┘
```

## 核心对象模型

1. **Security（证券主数据）**
2. **FinancialFact（财务事实表）**
3. **PriceMetric（价格与指标表）**
4. **Announcement（公告与文本表）**
5. **Position / Transaction（持仓与交易流水）**
6. **TradePlan（交易计划）**
7. **MacroSeries（宏观时间序列）**
8. **Snapshot（报告快照）**

## Snapshot Schema 约定

所有 snapshot 继承自 `src/common/models.py` 中的 `Snapshot` 基类，必须以 **结构化 JSON** 落盘：

```
data/reports/{report_type}/{ticker?}/{version}.json
```

### 基类字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `snapshot_id` | `str` | 全局唯一标识 |
| `report_type` | `str` | `market` / `portfolio` / `research` / `daily_review` / `plan_review` |
| `created_at` | `datetime` | 生成时间 |
| `version` | `str` | `YYYYMMDDhhmmss-{hash_prefix}` |
| `data_cutoff` | `date / datetime / None` | 数据截止日期 |
| `metadata` | `SourceMetadata` | 来源、获取时间、版本、权威层级、置信度 |

### `SourceMetadata`

| 字段 | 说明 |
|------|------|
| `source` | 数据来源标识 |
| `retrieved_at` | 获取时间 |
| `version` | 数据版本 |
| `tier` | 权威层级（1=官方披露，2=同花顺/iFinD，3=agent 聚合） |
| `confidence` | 置信度 0-1 |
| `url` / `notes` | 可选补充 |

### MVP Snapshot 类型

- **MarketSnapshot**：指数、市场宽度、成交额、板块热度、两融、北向/ETF 资金流、情绪分。
- **PortfolioSnapshot**：现金、总资产、持仓、行业暴露、回撤、波动率、收益率。
- **ResearchSnapshot**：个股六维分析、估值区间、假设、失效条件、PDF 路径、引用。
- **DailyReviewSnapshot**：今日要点、市场情绪、持仓风险、计划偏离、过期研究、关注清单。
- **PlanReviewSnapshot**：计划触发条件、偏离、建议、用户决策。

## 数据标准化约定

所有标准化表必须包含：

| 字段 | 说明 |
|------|------|
| `source` | 数据来源 |
| `retrieved_at` | 获取时间 |
| `version` | 版本号 |

## 模块职责

| 模块 | 职责 |
|------|------|
| `data_ingestion` | 外部 API 封装，只拉取原始数据 |
| `data_standardization` | 清洗、对齐、去重、版本化、证券代码标准化 |
| `analysis` | 评分、指标、风险计算 |
| `report_generation` | 基于 Jinja2 模板生成 Markdown 快照 |
| `cli` | Typer 命令行入口，编排任务，输出结构化 JSON |
| `common/skill_runner.py` | 统一封装 Kimi CLI skill 调用 |
| `common/snapshot_io.py` | snapshot JSON 读写与 schema 校验 |

## 报告快照命名

```
data/reports/{report_type}/{ticker?}/{version}.json
```

`version` 格式：`YYYYMMDDhhmmss-{hash_prefix}`

## CLI Worker JSON 输出

CLI 通过 `--format json` 进入 agent-callable 模式，所有命令统一返回：

```json
{
  "success": true,
  "message": "...",
  "snapshot_path": "...",
  "version": "..."
}
```

生成多个 snapshot 的命令（如 `update daily`）在 `snapshots` 数组中返回：

```json
{
  "success": true,
  "message": "Daily update completed.",
  "snapshots": [
    {"report_type": "market", "snapshot_path": "...", "version": "..."},
    {"report_type": "portfolio", "snapshot_path": "...", "version": "..."}
  ]
}
```

日志统一输出到 **stderr**，stdout 只保留 JSON，便于 agent 解析。

## Kimi CLI Skill 调用模式

`src/common/skill_runner.py` 封装 Kimi CLI 调用：

1. **自动定位 skill 目录**：优先 `skills/{name}/`，其次 `~/.kimi-code/plugins/managed/{name}/`。
2. **构造命令**：`kimi --skills-dir <dir> --prompt <prompt> --output-format stream-json --add-dir <project_root>`
3. **传递上下文**：通过 `[context]` JSON 块追加到 prompt。
4. **捕获输出**：解析 `stream-json` 的每行 JSON，返回 `{success, returncode, stdout, stderr, parsed_output}`。
5. **错误处理**：子进程超时、命令不存在、返回非零均返回结构化结果或抛出 `SkillRunnerError`。

示例：

```python
from src.common.skill_runner import run_skill

result = run_skill(
    prompt="查询 000725.SZ 当前股价",
    skill_name="kimi-datasource",
    timeout=120,
)
```

## 前端路由

| 路由 | 页面 |
|------|------|
| `/` | Dashboard 总览 |
| `/stock/:ticker` | 个股分析 |
| `/portfolio` | 持仓管理 |
| `/plans` | 交易计划 |
| `/macro` | 宏观月报 |

## 前端系统状态

Dashboard 通过 `fetch('/system-status.json')` 读取最新 snapshot 元数据，展示最近生成时间与版本。该文件由 `climbing update daily` 写入 `web/public/system-status.json`。

## 本地开发

```bash
# 后端
python -m venv .venv
pip install -r requirements.txt
python -m src.cli.main --help

# 前端
cd web
npm install
npm run dev
```

## 测试 seam

以 **“Python CLI worker → snapshot 文件”** 作为唯一集成测试 seam：

```
natural language intent
       ↓
   agent scheduling
       ↓
Python CLI command --format json
       ↓
snapshot file(s) on disk
       ↓
schema validation + downstream rendering
```

测试使用 `tests/fixtures/` 数据，避免依赖外部 API。
