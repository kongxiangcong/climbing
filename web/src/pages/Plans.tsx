import { useEffect, useState } from 'react'

import DataCard from '../components/DataCard'
import { fetchPlans, type PlanSummary } from '../services/api'

const statusColor: Record<string, string> = {
  draft: '#888',
  active: '#4caf50',
  partially_triggered: '#ff9800',
  fully_triggered: '#2196f3',
  assumption_broken: '#f44336',
  closed: '#9e9e9e',
  reviewed: '#673ab7',
}

function Plans() {
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchPlans()
      .then((data) => {
        setPlans(data.plans || [])
        setError(null)
      })
      .catch((err) => {
        setError(err.message)
        setPlans([])
      })
      .finally(() => setLoading(false))
  }, [])

  const activeCount = plans.filter((p) => p.status === 'active').length

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>交易计划</h2>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <DataCard title="计划总数" value={plans.length} />
        <DataCard title="激活计划" value={activeCount} note="状态为激活" />
        <DataCard title="草稿计划" value={plans.filter((p) => p.status === 'draft').length} />
      </div>

      {loading && <p>加载中...</p>}
      {error && <p style={{ color: '#d32f2f' }}>{error}</p>}
      {!loading && !error && plans.length === 0 && (
        <p>暂无交易计划，请运行 climbing plan create &lt;ticker&gt; --name &lt;name&gt; --confirm</p>
      )}

      {plans.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #444' }}>
              <th style={{ textAlign: 'left', padding: '8px' }}>名称</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>标的</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>方向</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>状态</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>目标价区间</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>仓位上限</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>复盘频率</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>版本</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((plan) => (
              <tr key={plan.plan_id} style={{ borderBottom: '1px solid #333' }}>
                <td style={{ padding: '8px' }}>{plan.name}</td>
                <td style={{ padding: '8px' }}>{plan.ticker}</td>
                <td style={{ padding: '8px' }}>{plan.direction}</td>
                <td style={{ padding: '8px', color: statusColor[plan.status] || '#fff' }}>
                  {plan.status_display}
                </td>
                <td style={{ padding: '8px' }}>
                  {plan.target_price_low ?? '-'} ~ {plan.target_price_high ?? '-'}
                </td>
                <td style={{ padding: '8px' }}>{plan.position_limit}%</td>
                <td style={{ padding: '8px' }}>{plan.review_frequency}</td>
                <td style={{ padding: '8px' }}>{plan.plan_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default Plans
