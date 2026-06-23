# Equity Report — Minimal Layout Spec

> 本文件为 `skills/stock-research` 的深度研报布局规范骨架。
> 完整视觉系统见 `output/report.css`。

## 使用方式

生成 PDF 前，先构造完整 HTML 文档：

1. 在 `<head>` 中内联 `output/report.css` 的全部内容（`<style>...</style>`）。
2. 根容器使用 `<div class="report-container">`（中文）或追加 `report-container-en`（英文）。
3. 按以下顺序组织页面：
   - P1: 封面（`.cover-split`）+ 摘要（`.exec-summary`）
   - P2: 数据摘要页（`.data-summary-page`）
   - 正文模块（每个 `.module-row` 从新页面开始）
   - 参考文献（`.references-list`）
   - 免责声明（`.disclaimer`）

## 封面结构

```html
<div class="cover-split">
  <div class="kimi-brand-bar">
    <span class="kimi-logo">Kimi Research</span>
    <span class="kimi-tagline">AI-Powered Equity Research</span>
  </div>
  <div class="cover-main">
    <div class="header-top">
      <div class="header-company">
        <span class="header-name">公司名称</span>
        <span class="header-code">Ticker</span>
      </div>
    </div>
    <h1 class="header-main-title">核心判断（8-15 字）</h1>
    <div class="cover-rating-line">
      <span class="cover-rating-badge">BUY / HOLD / SELL</span>
    </div>
    <div class="price-target-bar">...</div>
    <div class="cover-viewpoint">核心观点段落</div>
  </div>
  <div class="cover-sidebar">
    <div class="sidebar-title">关键数据</div>
    <div class="key-data-grid">...</div>
  </div>
</div>
```

## 摘要结构

```html
<div class="exec-summary">
  <div class="exec-summary-title">摘要</div>
  <div class="exec-summary-grid">
    <div class="exec-summary-item"><span class="es-label">投资论点</span><span class="es-content">...</span></div>
    <div class="exec-summary-item"><span class="es-label">财务亮点</span><span class="es-content">...</span></div>
    <div class="exec-summary-item"><span class="es-label">估值与目标价</span><span class="es-content">...</span></div>
    <div class="exec-summary-item"><span class="es-label">关键风险</span><span class="es-content">...</span></div>
  </div>
</div>
```

## 正文模块

每个模块：

```html
<div class="module-row">
  <h2 class="section-title">模块标题</h2>
  <p>...</p>
  <table class="report-table">...</table>
  <div class="data-source">数据来源：...</div>
</div>
```

## 参考文献

```html
<div class="module-row">
  <h2 class="section-title">参考文献与数据来源</h2>
  <div class="references-list">
    <div class="ref-item">[1] ...</div>
  </div>
</div>
```

## PDF 生成

优先使用 WeasyPrint 等支持 `@page` margin box 的工具将上述 HTML 转为 PDF。若环境不可用，可先生成占位 PDF 并记录警告。
