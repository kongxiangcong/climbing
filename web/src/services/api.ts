export interface SystemStatus {
  last_snapshot_at: string
  last_snapshot_version: string
  snapshots: Array<{
    report_type: string
    snapshot_path: string
    version: string
  }>
}

export interface SecurityMasterItem {
  ticker: string
  name: string
  market: string
  asset_class?: string
  sector?: string
  industry?: string
  tags: string[]
}

export interface PortfolioPosition {
  ticker: string
  quantity: number
  cost_basis: string
  market_price: string | null
  market_value: string | null
  unrealized_pnl: string | null
  realized_pnl: string
  account: string
}

export interface PortfolioExposure {
  category: string
  value_pct: string
}

export interface PortfolioSummary {
  last_snapshot_at: string
  version: string
  cash: string
  total_assets: string
  total_market_value: string
  unrealized_pnl: string
  realized_pnl: string
  sector_exposure: PortfolioExposure[]
  positions: PortfolioPosition[]
}

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export async function fetchSecurityMaster(): Promise<SecurityMasterItem[]> {
  try {
    const res = await fetch('/security-master.json')
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export async function fetchStockReport(ticker: string) {
  const res = await fetch(`${API_BASE}/reports/stock/${ticker}`)
  if (!res.ok) throw new Error('Failed to fetch stock report')
  return res.json()
}

export async function fetchPortfolioSummary(): Promise<PortfolioSummary | null> {
  // 优先调用后端 API；开发环境若无后端，回退读取 CLI 写入的静态摘要 JSON
  try {
    const res = await fetch(`${API_BASE}/portfolio/summary`)
    if (res.ok) return res.json()
  } catch {
    // fallthrough to static JSON
  }
  try {
    const res = await fetch('/portfolio-summary.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function fetchPlans() {
  const res = await fetch(`${API_BASE}/plans`)
  if (!res.ok) throw new Error('Failed to fetch plans')
  return res.json()
}

export async function fetchMacroReport() {
  const res = await fetch(`${API_BASE}/reports/macro/latest`)
  if (!res.ok) throw new Error('Failed to fetch macro report')
  return res.json()
}

export interface MarketSummary {
  last_snapshot_at: string
  version: string
  trade_date: string
  indices: Array<{
    ticker: string
    name: string
    close: string
    change_pct: string
  }>
  total_turnover: string | null
  breadth: Record<string, number>
  sector_heat: Array<{
    name: string
    score: number
    change_pct: string | null
  }>
  sentiment_score: number | null
  temperature_label: string
}

export async function fetchMarketSummary(): Promise<MarketSummary | null> {
  try {
    const res = await fetch('/market-summary.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function fetchSystemStatus(): Promise<SystemStatus | null> {
  try {
    const res = await fetch('/system-status.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}
