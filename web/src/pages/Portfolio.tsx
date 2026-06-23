import { useEffect, useState } from 'react'
import {
  fetchPortfolioSummary,
  type PortfolioSummary,
} from '../services/api'

function formatCurrency(value: string | null | undefined) {
  if (value === null || value === undefined) return '-'
  const num = parseFloat(value)
  if (Number.isNaN(num)) return value
  return `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function MetricCard({ label, value, tone }: { label: string; value: string; tone?: 'default' | 'positive' | 'negative' }) {
  const color =
    tone === 'positive'
      ? '#16a34a'
      : tone === 'negative'
        ? '#dc2626'
        : '#111827'
  return (
    <div
      style={{
        flex: '1 1 160px',
        minWidth: '140px',
        padding: '16px',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        background: '#fff',
      }}
    >
      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '20px', fontWeight: 600, color }}>{value}</div>
    </div>
  )
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString('zh-CN')
}

function Portfolio() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPortfolioSummary()
      .then((data) => {
        setSummary(data)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div style={{ padding: '16px 0' }}>加载中...</div>
  }

  if (!summary) {
    return (
      <div>
        <h2 style={{ marginBottom: '16px' }}>持仓管理</h2>
        <p>暂无持仓快照，请先运行 <code>climbing portfolio import-transactions &lt;file&gt;</code> 或 <code>climbing update daily</code>。</p>
      </div>
    )
  }

  const unrealized = parseFloat(summary.unrealized_pnl || '0')
  const realized = parseFloat(summary.realized_pnl || '0')

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>持仓管理</h2>

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <MetricCard label="总资产" value={formatCurrency(summary.total_assets)} />
        <MetricCard label="总市值" value={formatCurrency(summary.total_market_value)} />
        <MetricCard label="现金" value={formatCurrency(summary.cash)} />
        <MetricCard
          label="浮动盈亏"
          value={formatCurrency(summary.unrealized_pnl)}
          tone={unrealized >= 0 ? 'positive' : 'negative'}
        />
        <MetricCard
          label="已实现盈亏"
          value={formatCurrency(summary.realized_pnl)}
          tone={realized >= 0 ? 'positive' : 'negative'}
        />
      </div>

      <h3 style={{ marginBottom: '12px' }}>持仓明细</h3>
      {summary.positions.length === 0 ? (
        <p>当前无持仓。</p>
      ) : (
        <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>代码</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>数量</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>成本价</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>市价</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>市值</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>浮动盈亏</th>
                <th style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>已实现盈亏</th>
              </tr>
            </thead>
            <tbody>
              {summary.positions.map((p, idx) => {
                const unrealizedPnl = parseFloat(p.unrealized_pnl || '0')
                const realizedPnl = parseFloat(p.realized_pnl || '0')
                return (
                  <tr key={`${p.ticker}-${idx}`}>
                    <td style={{ padding: '10px', borderBottom: '1px solid #e5e7eb' }}>{p.ticker}</td>
                    <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{p.quantity}</td>
                    <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{formatCurrency(p.cost_basis)}</td>
                    <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{formatCurrency(p.market_price)}</td>
                    <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{formatCurrency(p.market_value)}</td>
                    <td
                      style={{
                        padding: '10px',
                        textAlign: 'right',
                        borderBottom: '1px solid #e5e7eb',
                        color: unrealizedPnl >= 0 ? '#16a34a' : '#dc2626',
                      }}
                    >
                      {formatCurrency(p.unrealized_pnl)}
                    </td>
                    <td
                      style={{
                        padding: '10px',
                        textAlign: 'right',
                        borderBottom: '1px solid #e5e7eb',
                        color: realizedPnl >= 0 ? '#16a34a' : '#dc2626',
                      }}
                    >
                      {formatCurrency(p.realized_pnl)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ marginBottom: '12px' }}>行业暴露</h3>
      {summary.sector_exposure.length === 0 ? (
        <p>暂无行业分布数据。</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {summary.sector_exposure.map((e) => (
            <li
              key={e.category}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px 0',
                borderBottom: '1px solid #e5e7eb',
              }}
            >
              <span>{e.category}</span>
              <span>{parseFloat(e.value_pct).toFixed(2)}%</span>
            </li>
          ))}
        </ul>
      )}

      <p style={{ marginTop: '24px', color: '#6b7280', fontSize: '12px' }}>
        版本：{summary.version} · 更新时间：{formatDateTime(summary.last_snapshot_at)}
      </p>
    </div>
  )
}

export default Portfolio
