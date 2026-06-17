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
| `data_standardization` | 清洗、对齐、去重、版本化 |
| `analysis` | 评分、指标、风险计算 |
| `report_generation` | 基于 Jinja2 模板生成 Markdown 快照 |
| `cli` | Typer 命令行入口，编排任务 |

## 报告快照命名

```
data/reports/{report_type}/{ticker?}/{version}.md
```

`version` 格式：`YYYYMMDDhhmmss-{hash_prefix}`

## 前端路由

| 路由 | 页面 |
|------|------|
| `/` | Dashboard 总览 |
| `/stock/:ticker` | 个股分析 |
| `/portfolio` | 持仓管理 |
| `/plans` | 交易计划 |
| `/macro` | 宏观月报 |

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
