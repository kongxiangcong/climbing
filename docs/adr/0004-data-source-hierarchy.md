# 数据源采用分层权威模型，capital_flow.py 拆分为取数 + agent 解释

Climbing 的事实数据采用多源获取，但遵循明确的权威层级：官方披露（央行、交易所、财政部等）> 同花顺 / iFinD 等专业数据终端 > agent 聚合数据（kimi-datasource / akshare / tushare 等）。冲突时以更高权威来源为准，并记录差异。个股研究以 kimi-datasource 为主，缺失时允许 agent 通过 akshare / tushare 补充并显式标注 `source` 和 `confidence`；持仓交易坚持券商/同花顺导出文件导入，不走 API 自动同步；MarketSnapshot 优先使用 kimi-datasource 日度接口，不足时用 akshare / tushare 补充。`capital_flow.py` 不再作为独立的 matplotlib 看板脚本，而是拆分为 Python 取数/标准化模块（负责从同花顺等来源拉取 M2、国债收益率、沪深300、两融数据并写入标准化事实表）和 agent skill（负责把事实解释为「资金面四问」并生成月报）。

## 状态

accepted

## 考虑的替代方案

1. **所有数据都走 kimi-datasource**：rejected。kimi-datasource 可能不支持板块资金流、个人持仓导出等场景。
2. **持仓数据用同花顺 API 自动同步**：rejected。存在授权合规和自动交易边界风险。
3. **capital_flow.py 整体升级为 agent skill**：rejected。M2、国债收益率、指数点位等是确定的事实，Python 取数更可靠；agent 只负责解释和叙事。

## 后果

- 每份标准化表和 snapshot 必须包含 `source`、`retrieved_at`、`version` 字段，多源场景下还需记录 `confidence` 和 `authority_tier`。
- 需要维护一个轻量的数据源注册表，记录每个指标的首选来源和 fallback 来源。
- `capital_flow.py` 需要重写为数据管道，matplotlib 图表可作为月报生成的可选输出，不再是主要职责。

---
