# 个股研究引擎采用改写后的 equity-researcher skill

个股全景分析不在 Climbing Python 代码中重新实现六维分析、估值或报告生成逻辑，而是把 `skills/equity-researcher/` 作为深度研究引擎：只保留 Equity Report 深度模式，输出 PDF 研报 + 符合 Climbing schema 的结构化 ResearchSnapshot。Climbing Python 端负责缓存判断、job 管理、Kimi CLI 调度、产物校验、版本追溯以及交易计划引用。这样可以把专业投研方法论（六维分析、DCF/可比估值、QA）封装在 skill 中，同时让 Climbing 保持本地优先、版本化、可追溯的核心约定。

## 状态

accepted

## 考虑的替代方案

1. **在 Climbing 内部用 Python 重写分析逻辑**： rejected。六维分析、估值模型、QA 规则已经在 equity-researcher skill 中高度成熟，重写成本高且容易失真。
2. **保留 Tear Sheet + Equity Report 双模式**： rejected。Tear Sheet 与深度研报在产物 schema 上不一致，会增加 Climbing 的解析和版本化复杂度；日常扫描可以通过缓存命中已生成的 ResearchSnapshot 快速响应。
3. **把任务丢到文件系统由长期 agent 消费**： rejected。需要额外维护 agent 生命周期和任务队列，不如 CLI 子进程阻塞调用简单可控。

## 后果

- 需要为 equity-researcher skill 编写 Climbing 适配版本，强制输出 `snapshot.json`、`references.json`、`qa_check.json`。
- Climbing 必须实现 snapshot schema 校验、minor/major 版本判断、job file 持久化。
- 个股研究依赖 Kimi agent 运行时和数据源 skill，离线环境下无法生成新研究（但可以读取已有 snapshot）。

---
