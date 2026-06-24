import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import DataCard from '../components/DataCard'
import {
  fetchDailyReviewSummary,
  fetchMarketSummary,
  fetchSecurityMaster,
  fetchSystemStatus,
  type DailyReviewSummary,
  type MarketSummary,
  type SecurityMasterItem,
  type SystemStatus,
} from '../services/api'

function formatChangePct(changePct: string): string {
  const value = parseFloat(changePct)
  if (Number.isNaN(value)) return changePct
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatTurnover(value: string | null): string {
  if (!value) return '-'
  const num = parseFloat(value)
  if (Number.isNaN(num)) return value
  if (num >= 1e8) return `${(num / 1e8).toFixed(2)} 亿`
  if (num >= 1e4) return `${(num / 1e4).toFixed(2)} 万`
  return `${num.toFixed(2)}`
}

function formatReviewNote(summary: DailyReviewSummary | null): string {
  if (!summary) return '运行日更后生成'
  const { pending_counts } = summary
  const parts: string[] = []
  if (pending_counts.stocks_needing_review > 0) {
    parts.push(`需复核 ${pending_counts.stocks_needing_review} 只`)
  }
  if (pending_counts.plan_deviations > 0) {
    parts.push(`偏离计划 ${pending_counts.plan_deviations} 条`)
  }
  if (pending_counts.expired_research > 0) {
    parts.push(`过期研究 ${pending_counts.expired_research} 条`)
  }
  return parts.length > 0 ? parts.join(' · ') : '暂无待复核事项'
}

function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [securities, setSecurities] = useState<SecurityMasterItem[]>([])
  const [marketSummary, setMarketSummary] = useState<MarketSummary | null>(null)
  const [dailyReview, setDailyReview] = useState<DailyReviewSummary | null>(null)

  useEffect(() => {
    fetchSystemStatus().then(setStatus)
    fetchSecurityMaster().then(setSecurities)
    fetchMarketSummary().then(setMarketSummary)
    fetchDailyReviewSummary().then(setDailyReview)
  }, [])

  const lastSnapshot = status
    ? `${new Date(status.last_snapshot_at).toLocaleString()} (${status.last_snapshot_version})`
    : '暂无'

  const watchlistNames =
    securities.length > 0
      ? securities.map((s) => s.name).join('、')
      : '运行 climbing update securities 后生成'

  const indexSummary = marketSummary?.indices
    .map((i) => `${i.name} ${formatChangePct(i.change_pct)}`)
    .join(' / ') ?? '运行日更后生成'

  const turnoverSummary = marketSummary?.total_turnover
    ? `成交额 ${formatTurnover(marketSummary.total_turnover)}`
    : ''

  const temperatureSummary = marketSummary
    ? `温度 ${marketSummary.temperature_label}${
        marketSummary.sentiment_score !== null
          ? ` (${(marketSummary.sentiment_score * 100).toFixed(0)})`
          : ''
      }`
    : ''

  const marketNote = [indexSummary, turnoverSummary, temperatureSummary]
    .filter(Boolean)
    .join(' · ')

  const reviewNote = formatReviewNote(dailyReview)
  const reviewHighlight = dailyReview?.highlights?.[0] ?? '暂无复盘摘要'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
        <h2>总览</h2>
        <Link to="/inspection"><button type="button">今日巡检</button></Link>
      </div>
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <DataCard
          title="关注标的"
          value={securities.length}
          note={watchlistNames}
        />
        <DataCard title="持仓数量" value={0} note="需导入持仓 CSV" />
        <DataCard title="激活计划" value={0} note="需创建交易计划" />
        <DataCard title="最新快照" value={lastSnapshot} note="运行日更后生成" />
        <DataCard
          title="市场概况"
          value={marketSummary?.trade_date ?? '-'}
          note={marketNote}
        />
        <DataCard
          title="今日复盘"
          value={dailyReview?.sentiment ?? '-'}
          note={`${reviewHighlight} | ${reviewNote}`}
        />
      </div>
    </div>
  )
}

export default Dashboard
