# 投研交易系统数据可获取性审核报告

> 审核对象：`climbing.md` 中描述的数据架构与数据需求  
> 验证标的：京东方A（000725.SZ）/ 京东方科技集团股份有限公司  
> 审核时间：2026-06-17  

---

## 一、核心发现

### 1.1 数据源名称存在偏差

`climbing.md` 中大量引用 **“同花顺 iFind”** 及其 `ifind_get_*` API。  
**当前实际可用的数据源并非同花顺 iFind，而是 `stock_finance_data`**。两者的 API 名称、参数命名不同，但覆盖的数据类型高度重合（行情、财务、股东、公告、预测、业务分部、财务指标等）。

### 1.2 数据可获取性总体评估

| 可用程度 | 数量级 | 说明 |
|---------|-------|------|
| ✅ 直接可用 | 约 25 项 | 通过 `stock_finance_data`、`yahoo_finance`、`world_bank_open_data`、`tianyancha`、`arxiv`、`scholar`、`WebSearch` 可直接获取 |
| ⚠️ 间接可用 / 需二次处理 | 约 12 项 | 舆情、政策、龙虎榜、大宗交易、ESG、专利等需通过 `WebSearch` + 抓取/解析获得；技术指标需基于价格数据用 pandas 计算 |
| ❌ 当前不可用 | 约 10 项 | Level 2 盘口/逐笔、主力资金流向、暗池/SEC 13F、券商持仓接口、用户本地数据等 |

---

## 二、已验证数据源清单（按 climbing.md 模块）

### 2.1 研报收集系统

| 数据项 | 实际可用性 | 实际 API | 验证结果 |
|--------|-----------|---------|---------|
| 公司基本信息 | ✅ | `stock_finance_data_get_stock_info` | 京东方A：注册资本370.44亿元，控股股东北京电控（2.96%），实控人北京市国资委（13.93%） |
| 财务报表（三表） | ✅ | `stock_finance_data_get_financial_statements` | 2024年报：总资产4299.78亿，净利润41.45亿，经营现金流477.38亿 |
| 业务分部数据 | ✅ | `stock_finance_data_get_stock_business_segmentation` | 显示器件业务占比78.75%，物联网创新16.14%，MLED 4.05% |
| 盈利预测 | ✅ | `stock_finance_data_get_forecast` | FY1净利润83.58亿，FY2 121.80亿，FY3 161.93亿 |
| 估值/财务指标 | ✅ | `stock_finance_data_get_stock_financial_index` | ROE 4.06%，毛利率15.20%，净利率2.09%，EPS 0.14元 |
| 股东信息 | ✅ | `stock_finance_data_get_holder_info` | 第一大股东北京国资运营10.97%，机构持股29.13%，股东户数100.01万户 |
| 公司公告 | ✅ | `stock_finance_data_get_stock_announcement` | 2026-05-01至2026-06-17返回36条公告，含PDF链接 |
| 日线行情 OHLCV | ✅ | `stock_finance_data_get_price` | 返回30个交易日数据，6月17日收盘价6.71元 |
| 复权价格 | ✅ | `stock_finance_data_get_price` | 支持 forward/backward/none 复权 |
| 周/月线 | ✅ | `stock_finance_data_get_price` | interval=W/M 支持 |
| 分钟线/实时行情 | ⚠️ 部分可用 | `stock_finance_data_get_stock_realtime_price` | 支持 close_summary/open_summary/realtime_price/realtime_tech；无独立分钟历史API |
| 美股行情 | ✅ | `yahoo_finance` | 支持 A/H/美 行情；京东方A验证可用 |
| 行业分类/可比公司 | ✅ | `stock_finance_data_get_stock_info` | comparing_company 字段存在（本次返回为空，需进一步确认） |
| 产业链图谱/智能选股 | ⚠️ 待确认 | `stock_finance_data_get_related_stock` | 多次尝试均返回 EMPTY_DATA，关键词策略需调整 |
| 宏观数据（GDP/CPI/贸易） | ✅ | `world_bank_open_data` | 中国GDP、CPI通胀、贸易净额、贸易占GDP比重均成功获取 |

### 2.2 追踪分析系统

| 数据项 | 实际可用性 | 实际 API/方法 | 验证结果 |
|--------|-----------|--------------|---------|
| 实时价格/涨跌幅 | ✅ | `stock_finance_data_get_stock_realtime_price` | 6月17日收盘涨停，涨幅10%，成交额1213.43亿元 |
| 主力资金流向 | ❌ | - | 无同花顺L2权限，无直接API |
| 融资融券余额 | ⚠️ 待确认 | `stock_finance_data_get_stock_financial_index` | 当前未明确返回 margin 字段，需进一步检查 |
| 北向资金持仓 | ⚠️ 待确认 | `stock_finance_data_get_holder_info` | holder_info 含机构分类，但北向字段未明确识别 |
| 龙虎榜/大宗交易 | ⚠️ 间接可用 | `WebSearch` | 无直接API，可通过搜索获取 |
| 技术指标 MA/EMA/MACD/KDJ/RSI/布林带/ATR | ✅ | Python pandas + `stock_finance_data_get_stock_realtime_price` (realtime_tech) | 实时技术面接口已内置部分指标；其余可用 pandas 计算 |
| 新闻舆情 | ✅ | `WebSearch` | 搜索“京东方A 000725 最新消息”返回新浪财经、东方财富、中财网、股吧等结果 |
| 社交媒体情绪 | ⚠️ 间接可用 | `WebSearch` + `FetchURL` | 可搜索股吧/雪球后抓取正文做情绪分析 |
| 分析师评级变动 | ✅ | `yahoo_finance_get_recommendations` | 当前 strongBuy 3家 / buy 4家 / hold 2家 |
| ESG评分 | ⚠️ 间接可用 | `WebSearch` | 无直接ESG API |
| 专利数据 | ⚠️ 间接可用 | `WebSearch` / 天眼查知识产权API | 无直接专利API |

### 2.3 交易计划系统

| 数据项 | 实际可用性 | 说明 |
|--------|-----------|------|
| 用户持仓/交易记录/资金 | ❌ | 需用户手动输入或券商API，当前环境无此能力 |
| 买卖五档盘口 | ❌ | 无Level 2/高级行情权限 |
| 订单流/逐笔成交 | ❌ | 无交易所Level 2数据 |
| 暗池交易/13F | ❌ | SEC EDGAR 数据源未在当前环境列出 |
| 期权链/隐含波动率 | ⚠️ 部分可用 | Yahoo Finance 期权链仅支持美股；A股权益数据需 WebSearch |
| Beta/相关系数/VaR/夏普/行业集中度 | ✅ | Python pandas/numpy 基于持仓和价格数据计算 |

### 2.4 学术/企业数据

| 数据项 | 实际可用性 | 实际 API | 验证结果 |
|--------|-----------|---------|---------|
| 学术论文 | ✅ | `arxiv_search_papers` / `scholar_search` | arXiv返回OLED论文；Scholar返回京东方/OLED/显示技术中文论文 |
| 企业工商/司法/知识产权/关联图谱 | ✅ | `tianyancha_api_call` | 已验证企业基本信息、历史股东信息可用；声称支持226个API |

---

## 三、重要差异与风险提醒

1. **同花顺 iFind ≠ stock_finance_data**  
   `climbing.md` 中的代码模板（如 `ifind_get_price`）在当前环境无法直接运行，需要改写为 `stock_finance_data_get_price` 等实际 API。

2. **实时/分钟数据能力有限**  
   无独立的分钟历史行情 API，分钟级数据通过 `realtime_price` 获取；且 `realtime_tech` 不支持港股、美股、ETF、科创板。

3. **A股权益类数据受限**  
   Yahoo Finance 的期权链、新闻 API 对 A股不稳定或不可用；A股权益数据需依赖 WebSearch。

4. **Level 2 / 主力资金 / 盘口数据缺失**  
   这是交易系统中非常关键的数据层，当前环境无法获取。若系统需要实时资金流向或逐笔成交，必须采购付费数据源（如交易所Level 2、同花顺iFind高级权限、Wind等）。

5. **产业链/智能选股 API 不稳定**  
   `stock_finance_data_get_related_stock` 对“显示面板”等关键词返回空数据，无法作为可靠的产业链构建工具。

6. **用户本地数据无接口**  
   持仓、交易记录、资金等必须通过外部导入或用户输入，无法自动同步。

---

## 四、已生成交付物

| 文件 | 说明 |
|------|------|
| `data_audit.csv` | 全量数据需求可获取性审计表（按 climbing.md 模块整理） |
| `data_verification_results.csv` | 逐个 API 实测结果、输出文件、样例数据 |
| `verify_*.csv` | 各 API 原始输出数据文件（共 20+ 个） |
| `data_audit_report.md` | 本报告 |

---

## 五、结论与建议

### 5.1 结论

- **60%-70% 的核心投研数据可直接获取**：行情、财务三表、业务分部、盈利预测、财务指标、股东信息、公告、宏观数据、企业工商、学术论文、新闻舆情等。
- **交易执行层面的微观结构数据严重缺失**：Level 2、主力资金、盘口、逐笔成交、暗池等无法获取。
- **技术指标与组合风险指标可基于已有数据自行计算**：无需额外数据源。

### 5.2 系统架构建议

基于当前实际能力，建议将系统定位为 **“投研研究与追踪分析系统”**，而非完整的 **“实时交易系统”**：

| 优先级 | 模块 | 可行度 |
|--------|------|--------|
| P0 | 研报收集器（财务/行情/公告/股东/预测） | 高 |
| P0 | 追踪分析面板（价格、技术指标、新闻舆情） | 高 |
| P1 | 组合风险管理（基于用户导入持仓 + Python计算） | 中 |
| P1 | 交易计划生成器（半自动，依赖用户输入） | 中 |
| P2 | 实时交易信号/高频策略 | 低（缺少L2数据） |

若后续需要完整交易执行能力，必须：
1. 接入券商 API 或采购 Wind/同花顺 iFind 高级权限；
2. 采购交易所 Level 2 行情；
3. 部署本地数据库与实时数据流处理。

---

*报告完成。*
