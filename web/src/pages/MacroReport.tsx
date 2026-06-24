import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import DataCard from '../components/DataCard'
import {
  fetchMacroReport,
  type MacroIndicator,
  type MacroReportData,
} from '../services/api'

const LABEL_TEXT: Record<string, string> = {
  overheated: '过热',
  neutral: '中性',
  cool: '偏冷',
}

const LABEL_COLOR: Record<string, string> = {
  overheated: '#ff6b6b',
  neutral: '#ffd93d',
  cool: '#6bcb77',
}

const CATEGORY_TEXT: Record<string, string> = {
  growth: '增长',
  inflation: '通胀',
  liquidity: '流动性',
  market_structure: '市场结构',
}

function IndicatorCard({ indicator }: { indicator: MacroIndicator }) {
  return (
    <DataCard
      title={indicator.name}
      value={`${indicator.value} ${indicator.unit}`}
      note={`来源: ${indicator.metadata.source} (T${indicator.metadata.tier ?? '-'})`}
    />
  )
}

function FactorPanel({
  category,
  label,
  indicators,
}: {
  category: string
  label: string
  indicators: MacroIndicator[]
}) {
  return (
    <div
      style={{
        background: '#1a1a1a',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '16px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
        }}
      >
        <h3 style={{ margin: 0 }}>{CATEGORY_TEXT[category]}</h3>
        <span
          style={{
            background: LABEL_COLOR[label] || '#888',
            color: '#000',
            padding: '4px 12px',
            borderRadius: '12px',
            fontSize: '0.875rem',
            fontWeight: 600,
          }}
        >
          {LABEL_TEXT[label] || label}
        </span>
      </div>
      {indicators.length === 0 ? (
        <div style={{ color: '#666', fontSize: '0.875rem' }}>暂无指标</div>
      ) : (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {indicators.map((ind) => (
            <IndicatorCard key={ind.name} indicator={ind} />
          ))}
        </div>
      )}
    </div>
  )
}

function MacroChart({
  indicatorHistory,
}: {
  indicatorHistory: Array<Record<string, number | string>>
}) {
  const keys = Object.keys(indicatorHistory[0] || {}).filter((k) => k !== 'period')
  const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00c49f']
  return (
    <div
      style={{
        background: '#1a1a1a',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '16px',
      }}
    >
      <h3 style={{ marginTop: 0 }}>关键指标趋势</h3>
      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={indicatorHistory}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="period" stroke="#888" />
            <YAxis stroke="#888" />
            <Tooltip
              contentStyle={{
                background: '#1a1a1a',
                border: '1px solid #333',
                color: '#eee',
              }}
            />
            <Legend />
            {keys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function MacroReport() {
  const [report, setReport] = useState<MacroReportData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchMacroReport()
      .then(setReport)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div>加载中...</div>
  }

  if (!report) {
    return (
      <div>
        暂无宏观月报数据，请运行{' '}
        <code>python -m src.cli.main update monthly --mock</code>
      </div>
    )
  }

  const byCategory = (category: string) =>
    report.indicators.filter((i) => i.category === category)

  return (
    <div>
      <h2 style={{ marginBottom: '16px' }}>宏观月报 · {report.report_month}</h2>
      <p style={{ color: '#888', marginBottom: '24px' }}>
        版本：{report.version} · 更新时间：
        {new Date(report.last_snapshot_at).toLocaleString('zh-CN')} · 来源：
        {report.source} (T{report.authority_tier ?? '-'})
      </p>

      <FactorPanel
        category="growth"
        label={report.growth_label}
        indicators={byCategory('growth')}
      />
      <FactorPanel
        category="inflation"
        label={report.inflation_label}
        indicators={byCategory('inflation')}
      />
      <FactorPanel
        category="liquidity"
        label={report.liquidity_label}
        indicators={byCategory('liquidity')}
      />
      <FactorPanel
        category="market_structure"
        label={report.market_structure_label}
        indicators={byCategory('market_structure')}
      />

      <div
        style={{
          background: '#1a1a1a',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '16px',
        }}
      >
        <h3 style={{ marginTop: 0 }}>资金面四问</h3>
        {report.four_questions.map((q) => (
          <div
            key={q.question_id}
            style={{
              marginBottom: '12px',
              padding: '12px',
              background: '#252525',
              borderRadius: '6px',
            }}
          >
            <div style={{ fontWeight: 600, color: '#ffd93d' }}>
              {q.question_id}：{q.question}
            </div>
            <div style={{ marginTop: '8px' }}>{q.answer}</div>
            {q.evidence.length > 0 && (
              <div
                style={{
                  fontSize: '0.8rem',
                  color: '#888',
                  marginTop: '4px',
                }}
              >
                证据：{q.evidence.join(' · ')}
              </div>
            )}
          </div>
        ))}
      </div>

      {report.indicator_history && report.indicator_history.length > 0 && (
        <MacroChart indicatorHistory={report.indicator_history} />
      )}

      {(report.summary || report.outlook) && (
        <div
          style={{
            background: '#1a1a1a',
            borderRadius: '8px',
            padding: '20px',
            marginBottom: '16px',
          }}
        >
          {report.summary && (
            <>
              <h3 style={{ marginTop: 0 }}>综合判断</h3>
              <p>{report.summary}</p>
            </>
          )}
          {report.outlook && (
            <>
              <h4>展望</h4>
              <p>{report.outlook}</p>
            </>
          )}
          {report.risks && report.risks.length > 0 && (
            <>
              <h4>风险提示</h4>
              <ul>
                {report.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default MacroReport
