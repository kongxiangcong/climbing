# Climbing — 个人投研研究与追踪分析系统

> 一个面向个人投资者的 A 股研究与持仓跟踪工具。做研究，不做交易执行；做计划与追踪，不做自动下单。

## 项目定位

基于公开披露数据、结构化市场数据、宏观数据和辅助情报，为个人投资者提供：

1. **个股全景分析与估值报告** —— 输入股票代码，生成可验证的研究档案与结论
2. **持仓管理** —— 导入持仓与交易流水，自动计算收益、风险、集中度
3. **交易计划创建与跟踪** —— 把研究结论沉淀为结构化计划，并持续跟踪偏离
4. **市场与宏观月报** —— 增长、通胀、流动性、市场结构四栏因子面板

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（前端开发）

### 安装后端依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 验证安装

```bash
python -c "from src.common.config import settings; print(settings.project_name)"
python -m src.cli.main --help
```

### 启动前端开发服务器

```bash
cd web
npm install
npm run dev
```

## 项目结构

```
climbing/
├── config/               # YAML 配置文件
├── data/                 # 数据目录（raw / standardized / features / reports / user）
├── docs/                 # PRD、架构说明、数据审核报告
├── notebooks/            # 探索性分析
├── scripts/              # 日更、事件触发、月报脚本
├── src/                  # Python 后端源码
│   ├── common/           # 配置、日志、路径、Pydantic 模型
│   ├── data_ingestion/   # 数据采集客户端
│   ├── data_standardization/  # 数据标准化与版本化
│   ├── analysis/         # 分析引擎与评分器
│   ├── report_generation/# 报告生成
│   └── cli/              # 命令行入口
├── tests/                # 测试
└── web/                  # React + TypeScript 前端
```

## 数据流

```
采集 → 标准化 → 版本化 → 特征计算 → 规则引擎 → 报告生成 → 人工修订 → 快照归档
```

所有标准化数据保留 `source`、`retrieved_at`、`version` 字段，确保来源可追踪。

## 核心原则

- **本地优先**：数据默认落盘，不依赖外部数据库
- **批处理优先**：日更、事件驱动、月更三种任务
- **版本化**：报告与数据快照带版本号，支持回溯
- **边界清晰**：不接入券商 API、不做自动下单、不做盘中微观结构博弈

## 文档

- [产品需求文档](docs/prd.md)
- [技术架构](docs/architecture.md)
- [数据可获取性审核](docs/data/data_audit_report.md)

## 许可证

个人学习研究使用。所有数据遵循各自来源的使用协议，Yahoo Finance 等数据不得再分发。
