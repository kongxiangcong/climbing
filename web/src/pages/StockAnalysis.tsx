import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'

import DataCard from '../components/DataCard'
import { fetchStockReport, type ResearchSnapshot } from '../services/api'

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ marginBottom: '12px', fontSize: '1.1rem' }}>{title}</h3>
      {children}
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p style={{ color: '#666' }}>暂无数据</p>
  return (
    <ul style={{ paddingLeft: '20px', lineHeight: 1.8 }}>
      {items.map((item, idx) => (
        <li key={idx}>{item}</li>
      ))}
    </ul>
  )
}

function StockAnalysis() {
  const { ticker } = useParams()
  const [report, setReport] = useState<ResearchSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /* eslint-disable react-hooks/set-state-in-effect -- fetching data on ticker change requires local state updates */
  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    fetchStockReport(ticker)
      .then((data) => {
        setReport(data)
        setError(null)
      })
      .catch((err) => {
        setReport(null)
        setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [ticker])
  /* eslint-enable react-hooks/set-state-in-effect */

  if (!ticker) {
    return (
      <div>
        <h2 style={{ marginBottom: '16px' }}>个股分析</h2>
        <p>当前标的：未选择</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div>
        <h2 style={{ marginBottom: '16px' }}>个股分析</h2>
        <p>加载 {ticker} 研报中...</p>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div>
        <h2 style={{ marginBottom: '16px' }}>个股分析</h2>
        <p>当前标的：{ticker}</p>
        <p style={{ color: '#d32f2f' }}>
          {error || `暂无 ${ticker} 研报快照，请运行 climbing analyze stock ${ticker} --mock`}
        </p>
      </div>
    )
  }

  const coreConclusion = report.core_narrative?.core_viewpoint || report.summary
  const risks = report.risks_typed ?? report.risks.map((r) => ({ risk_type: '', description: r, impact: 'Medium' as const, probability: 'Medium' as const }))

  return (
    <div>
      <h2 style={{ marginBottom: '8px' }}>个股分析</h2>
      <p style={{ color: '#888', marginBottom: '24px' }}>
        当前标的：{report.ticker} · 版本 {report.version}
      </p>

      <SectionCard title="核心结论">
        <p style={{ lineHeight: 1.8 }}>{coreConclusion}</p>
      </SectionCard>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <DataCard
          title="目标价下限"
          value={report.target_price_low ?? '-'}
        />
        <DataCard
          title="目标价上限"
          value={report.target_price_high ?? '-'}
        />
        <DataCard
          title="估值方法"
          value={report.valuation.method}
        />
        <DataCard
          title="当前价"
          value={report.stock_price_data?.current_price ?? '-'}
        />
      </div>

      <SectionCard title="核心假设">
        <BulletList items={report.assumptions} />
      </SectionCard>

      <SectionCard title="六维分析证据">
        {report.six_dimensions_typed?.length ? (
          report.six_dimensions_typed.map((dim) => (
            <div key={dim.dimension_id} style={{ marginBottom: '12px' }}>
              <strong>
                {dim.dimension_id} {dim.dimension_name}
              </strong>
              <p style={{ margin: '4px 0', lineHeight: 1.6 }}>{dim.conclusion}</p>
              {dim.key_data_support.length > 0 && (
                <ul style={{ paddingLeft: '20px', color: '#888', fontSize: '0.875rem' }}>
                  {dim.key_data_support.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))
        ) : (
          <BulletList items={Object.values(report.six_dimensions)} />
        )}
      </SectionCard>

      <SectionCard title="失效条件">
        <BulletList items={report.invalidation_conditions} />
      </SectionCard>

      <SectionCard title="风险提示">
        {report.risks_typed ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #444' }}>
                <th style={{ textAlign: 'left', padding: '8px' }}>风险类型</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>描述</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>影响</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>概率</th>
              </tr>
            </thead>
            <tbody>
              {risks.map((r, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #333' }}>
                  <td style={{ padding: '8px' }}>{r.risk_type || '-'}</td>
                  <td style={{ padding: '8px' }}>{r.description}</td>
                  <td style={{ padding: '8px' }}>{r.impact}</td>
                  <td style={{ padding: '8px' }}>{r.probability}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <BulletList items={report.risks} />
        )}
      </SectionCard>

      {report.scenario_analysis && Object.keys(report.scenario_analysis).length > 0 && (
        <SectionCard title="情景分析">
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            {Object.entries(report.scenario_analysis).map(([name, scenario]) => (
              <DataCard
                key={name}
                title={name}
                value={scenario.implied_market_cap.toLocaleString()}
                note={`概率 ${(scenario.probability * 100).toFixed(0)}% · 目标 PE ${scenario.target_pe}`}
              />
            ))}
          </div>
        </SectionCard>
      )}

      {report.pdf_path && (
        <SectionCard title="完整报告">
          <a href={report.pdf_path} target="_blank" rel="noopener noreferrer">
            查看 PDF 研报
          </a>
        </SectionCard>
      )}
    </div>
  )
}

export default StockAnalysis
