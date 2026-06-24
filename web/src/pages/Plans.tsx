import { Fragment, useEffect, useMemo, useState } from 'react'

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

const deviationColor: Record<string, string> = {
  slight: '#fff',
  moderate: '#ff9800',
  severe: '#f44336',
}

const deviationBg: Record<string, string> = {
  slight: 'transparent',
  moderate: 'rgba(255, 152, 0, 0.08)',
  severe: 'rgba(244, 67, 54, 0.12)',
}

function Plans() {
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null)
  const [showDeviatedOnly, setShowDeviatedOnly] = useState(false)

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

  const activeCount = useMemo(
    () => plans.filter((p) => p.status === 'active').length,
    [plans]
  )

  const deviatedCount = useMemo(
    () => plans.filter((p) => p.deviation_level === 'moderate' || p.deviation_level === 'severe').length,
    [plans]
  )

  const displayedPlans = useMemo(() => {
    if (!showDeviatedOnly) return plans
    return plans.filter(
      (p) => p.deviation_level === 'moderate' || p.deviation_level === 'severe'
    )
  }, [plans, showDeviatedOnly])

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>交易计划</h2>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <DataCard title="计划总数" value={plans.length} />
        <DataCard title="激活计划" value={activeCount} note="状态为激活" />
        <DataCard title="草稿计划" value={plans.filter((p) => p.status === 'draft').length} />
        <DataCard
          title="偏离计划"
          value={deviatedCount}
          note="需复核"
        />
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showDeviatedOnly}
            onChange={(e) => setShowDeviatedOnly(e.target.checked)}
          />
          <span>仅显示偏离</span>
        </label>
      </div>

      {loading && <p>加载中...</p>}
      {error && <p style={{ color: '#d32f2f' }}>{error}</p>}
      {!loading && !error && plans.length === 0 && (
        <p>暂无交易计划，请运行 climbing plan create &lt;ticker&gt; --name &lt;name&gt; --confirm</p>
      )}

      {displayedPlans.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #444' }}>
              <th style={{ textAlign: 'left', padding: '8px' }}>名称</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>标的</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>方向</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>状态</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>目标价区间</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>仓位上限</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>偏离等级</th>
              <th style={{ textAlign: 'left', padding: '8px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {displayedPlans.map((plan) => {
              const level = plan.deviation_level
              const isExpanded = expandedPlanId === plan.plan_id
              return (
                <Fragment key={plan.plan_id}>
                  <tr
                    key={plan.plan_id}
                    style={{
                      borderBottom: '1px solid #333',
                      backgroundColor: level ? deviationBg[level] : 'transparent',
                    }}
                  >
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
                    <td
                      style={{
                        padding: '8px',
                        color: level ? deviationColor[level] : '#fff',
                        fontWeight: level ? 'bold' : 'normal',
                      }}
                    >
                      {level ? level.toUpperCase() : '-'}
                    </td>
                    <td style={{ padding: '8px' }}>
                      <button
                        onClick={() =>
                          setExpandedPlanId(isExpanded ? null : plan.plan_id)
                        }
                        style={{
                          padding: '4px 8px',
                          backgroundColor: '#333',
                          color: '#fff',
                          border: '1px solid #555',
                          borderRadius: '4px',
                          cursor: 'pointer',
                        }}
                      >
                        {isExpanded ? '收起复核' : '查看复核'}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${plan.plan_id}-review`}>
                      <td colSpan={8} style={{ padding: '12px 8px', backgroundColor: '#1a1a1a' }}>
                        <div style={{ marginBottom: '8px' }}>
                          <strong>偏离分数：</strong>
                          {plan.deviation_score ?? '-'}
                          {plan.latest_price && (
                            <span style={{ marginLeft: '16px' }}>
                              <strong>最新价：</strong> {plan.latest_price}
                            </span>
                          )}
                        </div>
                        {(plan.deviation_reasons && plan.deviation_reasons.length > 0) && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong>触发条件：</strong>
                            <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                              {plan.deviation_reasons.map((reason, idx) => (
                                <li key={idx}>{reason}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {plan.recommendation && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong>建议：</strong> {plan.recommendation}
                          </div>
                        )}
                        {plan.suggested_action && (
                          <div>
                            <strong>下一步：</strong> {plan.suggested_action}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default Plans
