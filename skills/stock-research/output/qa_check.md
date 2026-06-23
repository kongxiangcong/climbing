# stock-research — QA 规范

> 本文件定义 `skills/stock-research/` 生成深度研报后的质量检查标准。
> Python worker 会在落盘前运行 `src/common/snapshot_validator.py` 进行结构预检；
> 人工 QA 或 agent self-check 时参考本文件。

---

## 结构预检（自动）

运行：

```bash
python -m src.common.snapshot_validator data/reports/equity/{ticker}/{version}/snapshot.json --json
```

必须通过的检查项：

- `metadata` — Section I 元数据完整（公司名、市场、最新财报期、基准指数）。
- `core_narrative` — 核心投资叙事非空，且不能包含“占位”字样。
- `six_dimensions` — 六维分析完整，6 个维度均有结论。
- `investment_logic` — 短期与长期投资逻辑均包含多头/空头因子。
- `investment_thesis_table` — 投资论点综合分析表恰好 4 行。
- `company_overview` — 公司概览模块存在。
- `financial_data` — 财务数据包含利润表、关键比率、盈利质量信号。
- `valuation_data` — 估值数据存在（L1 可比公司或 L2 DCF）。
- `catalyst_calendar` — 催化剂日历 ≥4 个事件，≥2 个 High，包含下次财报。
- `scenario_analysis` — 包含 optimistic / base_case / pessimistic。
- `risks` — 风险列表非空。
- `industry_supply_chain` — 行业与产业链模块存在。
- `stock_price_data` — 股价与交易数据模块存在。

---

## A-Tier Checks（任一项失败即禁止交付）

| 编号 | 检查项 | 标准 |
|------|--------|------|
| A1 | 核心叙事 | `core_narrative.core_viewpoint` 明确给出公司地位、财务亮点、估值判断、主要风险 |
| A2 | 六维完整性 | 6 个维度均含结论、`so_what` 与 `key_data_support` |
| A3 | 投资论点表 | 4 行 × 6 列（维度、多头、空头、关键假设、拐点信号、判断）完整 |
| A4 | 多空平衡 | 短期与长期均至少包含 1 个 bear factor |
| A5 | 催化剂 | ≥4 个事件，≥2 个 High，必须包含下次财报 |
| A6 | 数据来源 | 所有财务/估值/行业数据标注 `source` 与权威层级（Tier 1/2/3） |
| A7 | 无占位数据 | 不允许“占位”“待补充”“TODO”等出现在核心字段 |
| A8 | 情景概率 | optimistic + base_case + pessimistic 概率之和为 100% |
| A9 | 估值交叉验证 | 至少使用两种估值方法并给出综合判断 |
| A10 | 风险量化 | 每个风险包含 `impact` / `probability` 及 `monitoring_signal` |

---

## B-Tier Checks（>3 项失败禁止交付）

| 编号 | 检查项 | 标准 |
|------|--------|------|
| B1 | 可比公司 | ≥3 家可比公司，含市值、PE、PB、PS/EV-EBITDA |
| B2 | 一致预期 | 包含覆盖机构数、EPS/营收预期、修正趋势 |
| B3 | 历史估值带 | PE/PB 历史分位 |
| B4 | DCF（L2） | WACC、永续增长率、5 年 FCF 预测、终值、股权价值 |
| B5 | 敏感性矩阵 | WACC × Terminal Growth 矩阵，base case 高亮 |
| B6 | 公司分部 | 业务分部收入、增速、毛利率 |
| B7 | 盈利质量 | OCF/净利润、非经常性损益、营运资本分析 |
| B8 | 产业链 | 上中下游节点 ≥4 层，使用真实公司名 |
| B9 | 风险数量 | ≥4 个结构化风险，覆盖行业/公司/财务/宏观 |
| B10 | 情景量化 | 每个情景给出营收、净利润、目标 PE、隐含市值 |

---

## C-Tier Checks（记录失败，不阻塞交付）

| 编号 | 检查项 | 标准 |
|------|--------|------|
| C1 | 段落质量 | 每段分析 3-5 句话，避免只有 bullet |
| C2 | 数据时效 | 使用最近财报与行情数据 |
| C3 | 引用数量 | references.json ≥5 条 |
| C4 | Exhibit 编号 | 图表/表格编号连续 |
| C5 | WACC 合理性 | 处于行业常见区间 |
| C6 | 终端价值占比 | 终值占 EV 50-70%，>80% 需特别说明 |

---

## 修复流程

1. 先修复结构预检失败项。
2. 再按 A-Tier → B-Tier → C-Tier 顺序处理。
3. 每次修改后重新运行 `snapshot_validator`。
4. 所有 A-Tier 通过且 B-Tier 失败 ≤3 项，方可交付。
