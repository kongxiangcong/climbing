export interface SystemStatus {
  last_snapshot_at: string
  last_snapshot_version: string
  snapshots: Array<{
    report_type: string
    snapshot_path: string
    version: string
  }>
}

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export async function fetchStockReport(ticker: string) {
  const res = await fetch(`${API_BASE}/reports/stock/${ticker}`)
  if (!res.ok) throw new Error('Failed to fetch stock report')
  return res.json()
}

export async function fetchPortfolioSummary() {
  const res = await fetch(`${API_BASE}/portfolio/summary`)
  if (!res.ok) throw new Error('Failed to fetch portfolio summary')
  return res.json()
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

export async function fetchSystemStatus(): Promise<SystemStatus | null> {
  try {
    const res = await fetch('/system-status.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}
