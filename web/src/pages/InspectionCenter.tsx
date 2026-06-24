import { useEffect, useState } from 'react'
import DataCard from '../components/DataCard'
import {
  fetchInspectionSummary,
  runInspection,
  type InspectionSnapshot,
  type RiskReminder,
} from '../services/api'

function severityLabel(severity: RiskReminder['severity']): string {
  if (severity === 'critical') return '重点'
  if (severity === 'warning') return '提醒'
  return '信息'
}

function formatMacroSummary(data: Record<string, unknown>): string {
  const reportMonth = data.report_month ? String(data.report_month) : '暂无'
  const labels = [data.growth_label, data.liquidity_label, data.market_structure_label]
    .filter(Boolean)
    .map(String)
    .join(' / ')
  return labels ? `${reportMonth} · ${labels}` : reportMonth
}

function EmptyLine({ text }: { text: string }) {
  return <div style={{ color: '#777', fontSize: '0.875rem' }}>{text}</div>
}

function InspectionCenter() {
  const [inspection, setInspection] = useState<InspectionSnapshot | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchInspectionSummary().then(setInspection)
  }, [])

  async function handleRunInspection() {
    setLoading(true)
    try {
      const next = await runInspection('climbing')
      setInspection(next)
    } finally {
      setLoading(false)
    }
  }

  const summary = inspection?.summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'center' }}>
        <div>
          <h2 style={{ marginBottom: '8px' }}>巡检中心</h2>
          <div style={{ color: '#888', fontSize: '0.875rem' }}>
            {inspection ? `${inspection.trade_date} · ${inspection.version}` : '暂无巡检快照'}
          </div>
        </div>
        <button type="button" onClick={handleRunInspection} disabled={loading}>
          {loading ? '巡检中' : '今日巡检'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <DataCard title="市场状态" value={summary ? summary.market_status : '-'} />
        <DataCard title="持仓状态" value={summary ? summary.portfolio_status : '-'} />
        <DataCard title="偏离计划" value={summary?.plan_deviations ?? 0} />
        <DataCard title="过期研究" value={summary?.expired_research ?? 0} />
        <DataCard title="待复核股票" value={summary?.stocks_needing_review ?? 0} />
        <DataCard
          title="宏观摘要"
          value={inspection ? formatMacroSummary(inspection.macro_summary) : '-'}
        />
      </div>

      <section>
        <h3 style={{ marginBottom: '12px' }}>软性风险提醒</h3>
        <div style={{ display: 'grid', gap: '10px' }}>
          {inspection?.risk_reminders.length ? (
            inspection.risk_reminders.map((reminder) => (
              <div
                key={`${reminder.code}-${reminder.title}`}
                style={{ border: '1px solid #333', borderRadius: '8px', padding: '12px', background: '#1a1a1a' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                  <strong>{reminder.title}</strong>
                  <span style={{ color: reminder.severity === 'critical' ? '#ff8a8a' : '#d6c36a' }}>
                    {severityLabel(reminder.severity)}
                  </span>
                </div>
                <div style={{ color: '#aaa', marginTop: '6px' }}>{reminder.detail}</div>
              </div>
            ))
          ) : (
            <EmptyLine text="暂无风险提醒" />
          )}
        </div>
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
        <div>
          <h3 style={{ marginBottom: '12px' }}>偏离计划</h3>
          <div style={{ display: 'grid', gap: '8px' }}>
            {inspection?.plan_deviations.length ? (
              inspection.plan_deviations.map((item) => (
                <div key={`${item.plan_id}-${item.reason}`} style={{ color: '#ddd' }}>
                  <strong>{item.plan_id}</strong> · {item.reason}
                </div>
              ))
            ) : (
              <EmptyLine text="暂无偏离计划" />
            )}
          </div>
        </div>

        <div>
          <h3 style={{ marginBottom: '12px' }}>过期研究</h3>
          <div style={{ display: 'grid', gap: '8px' }}>
            {inspection?.stale_research.length ? (
              inspection.stale_research.map((item) => (
                <div key={`${item.ticker}-${item.reason}`} style={{ color: '#ddd' }}>
                  <strong>{item.ticker}</strong> · {item.reason}
                </div>
              ))
            ) : (
              <EmptyLine text="暂无过期研究" />
            )}
          </div>
        </div>

        <div>
          <h3 style={{ marginBottom: '12px' }}>待复核股票</h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {inspection?.watchlist.length ? (
              inspection.watchlist.map((ticker) => (
                <span key={ticker} style={{ border: '1px solid #333', borderRadius: '6px', padding: '4px 8px' }}>
                  {ticker}
                </span>
              ))
            ) : (
              <EmptyLine text="暂无待复核股票" />
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

export default InspectionCenter
