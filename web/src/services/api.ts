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

export interface Valuation {
  method: string
  value_low: string | null
  value_high: string | null
  assumptions: string[]
}

export interface RiskItem {
  risk_type: string
  description: string
  impact: 'High' | 'Medium' | 'Low'
  probability: 'High' | 'Medium' | 'Low'
  monitoring_signal?: string
}

export interface DimensionAnalysis {
  dimension_id: string
  dimension_name: string
  conclusion: string
  key_data_support: string[]
  so_what: string
}

export interface Scenario {
  probability: number
  assumptions: string
  revenue: number
  net_income: number
  target_pe: number
  implied_market_cap: number
}

export interface CatalystEvent {
  event_date: string
  event: string
  importance: 'High' | 'Medium' | 'Low'
  impact_analysis: string
  market_expectation: string
  source: string
}

export interface ResearchSnapshot {
  snapshot_id: string
  report_type: 'research'
  version: string
  created_at: string
  ticker: string
  summary: string
  core_narrative?: {
    core_narrative: string
    main_title: string
    sub_title: string
    core_viewpoint: string
  }
  six_dimensions: Record<string, string>
  six_dimensions_typed?: DimensionAnalysis[]
  investment_logic?: {
    short_term: {
      bull_factors: Array<{ description: string; data_support: string }>
      bear_factors: Array<{ description: string; risk_level: string }>
    }
    long_term: {
      bull_factors: Array<{ description: string; data_support: string }>
      bear_factors: Array<{ description: string; risk_level: string }>
    }
  }
  investment_thesis_table?: Array<{
    dimension: string
    bull_arguments: string
    bear_arguments: string
    key_assumption: string
    turning_point_signal: string
    judgment: string
  }>
  company_overview?: {
    background: Record<string, string>
    business_model: Record<string, string>
    recent_developments: Record<string, string>
    business_segments: Array<{
      segment_name: string
      revenue: number
      revenue_pct: number
      yoy_growth: number
      gross_margin: number
    }>
  }
  financial_data?: {
    income_statement: Record<string, number>
    balance_sheet_highlights: Record<string, number>
    cash_flow_highlights: Record<string, number>
    earnings_quality_signals: string[]
    key_ratios: Record<string, Record<string, number>>
  }
  valuation: Valuation
  valuation_data?: {
    valuation_table: Record<string, number>
    consensus_expectations?: {
      coverage_count: number
      eps_forecast: number
      revenue_forecast: number
      revision_trend: string
      peg?: number
    }
    comparable_companies: Array<{
      name: string
      ticker: string
      market_cap: number
      pe?: number
      pb?: number
      ps?: number
      ev_ebitda?: number
    }>
    industry_average: Record<string, number>
    premium_discount_analysis: string
    dcf?: {
      wacc: number
      terminal_growth: number
      fcf_projections: number[]
      terminal_value: number
      enterprise_value: number
      equity_value_per_share: number
      sensitivity_matrix: Record<string, Record<string, number>>
    }
    historical_band?: {
      pe_band: Record<string, number>
      pb_band: Record<string, number>
    }
    valuation_synthesis?: string
  }
  catalyst_calendar?: CatalystEvent[]
  scenario_analysis?: Record<string, Scenario>
  risks: string[]
  risks_typed?: RiskItem[]
  assumptions: string[]
  invalidation_conditions: string[]
  target_price_low: string | null
  target_price_high: string | null
  industry_supply_chain?: {
    industry_overview: string
    market_concentration: string
    pricing_power: string
    entry_barriers: string
    competitive_trend: string
    supply_chain: Record<string, Array<{ name: string; role: string }>>
  }
  stock_price_data?: {
    current_price: number
    high_52w: number
    low_52w: number
    market_cap: number
    pe_ttm: number
    pb: number
    daily_volume: number
    turnover_rate: number
    beta: number
    dividend_yield: number
  }
  pdf_path: string | null
  references: Array<{ title: string; url?: string; source?: string; tier?: number }>
}

export interface MacroIndicator {
  name: string
  value: number | string
  unit: string
  period: string
  yoy_change: number | null
  mom_change: number | null
  category: 'growth' | 'inflation' | 'liquidity' | 'market_structure'
  metadata: {
    source: string
    retrieved_at: string
    tier: number | null
    authority_tier?: number | null
  }
}

export interface CapitalFlowAssessment {
  question_id: 'Q1' | 'Q2' | 'Q3' | 'Q4'
  question: string
  answer: string
  evidence: string[]
  label: 'overheated' | 'neutral' | 'cool'
}

export interface MacroReportData {
  report_month: string
  version: string
  last_snapshot_at: string
  source: string
  retrieved_at: string
  authority_tier: number | null
  indicators: MacroIndicator[]
  indicator_history?: Array<Record<string, number | string>>
  four_questions: CapitalFlowAssessment[]
  growth_label: 'overheated' | 'neutral' | 'cool'
  inflation_label: 'overheated' | 'neutral' | 'cool'
  liquidity_label: 'overheated' | 'neutral' | 'cool'
  market_structure_label: 'overheated' | 'neutral' | 'cool'
  summary?: string
  outlook?: string
  risks?: string[]
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

export async function fetchStockReport(ticker: string): Promise<ResearchSnapshot> {
  // 优先调用后端 API；开发环境若无后端，回退读取 CLI 写入的静态快照
  try {
    const res = await fetch(`${API_BASE}/reports/stock/${ticker}`)
    if (res.ok) return res.json()
  } catch {
    // fallthrough to static JSON
  }
  try {
    const res = await fetch(`/reports/equity/${ticker}/snapshot.json`)
    if (!res.ok) throw new Error(`Failed to fetch stock report for ${ticker}`)
    return res.json()
  } catch {
    throw new Error(`Failed to fetch stock report for ${ticker}`)
  }
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

export interface PlanSummary {
  plan_id: string
  name: string
  ticker: string
  direction: 'long' | 'short'
  status: string
  status_display: string
  plan_version: string
  target_price_low: string | null
  target_price_high: string | null
  position_limit: string
  risk_budget: string
  review_frequency: string
  research_version: string
  updated_at: string
  execution_records_count?: number
  deviation_score?: number | null
  deviation_level?: 'slight' | 'moderate' | 'severe' | null
  deviation_reasons?: string[]
  requires_review?: boolean
  latest_price?: string | null
  recommendation?: string | null
  suggested_action?: string | null
  latest_review_version?: string | null
}

export interface PlansSummary {
  last_updated_at: string
  count: number
  plans: PlanSummary[]
}

export interface DeviationAlert {
  plan_id: string
  reason: string
  severity: string
}

export interface ResearchAlert {
  ticker: string
  reason: string
}

export interface DailyReviewSummary {
  last_snapshot_at: string
  version: string
  trade_date: string
  highlights: string[]
  sentiment: string
  portfolio_risk: Record<string, unknown>
  plan_deviations: DeviationAlert[]
  stale_research: ResearchAlert[]
  watchlist: string[]
  pending_counts: {
    stocks_needing_review: number
    plan_deviations: number
    expired_research: number
  }
}

export async function fetchPlans(): Promise<PlansSummary> {
  // 开发环境若无后端，回退读取 CLI 写入的静态 plans.json
  try {
    const res = await fetch(`${API_BASE}/plans`)
    if (res.ok) return res.json()
  } catch {
    // fallthrough to static JSON
  }
  try {
    const res = await fetch('/plans.json')
    if (!res.ok) throw new Error('Failed to fetch plans')
    return res.json()
  } catch {
    throw new Error('Failed to fetch plans')
  }
}

export async function fetchDailyReviewSummary(): Promise<DailyReviewSummary | null> {
  try {
    const res = await fetch('/daily-review-summary.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function fetchMacroReport(): Promise<MacroReportData | null> {
  try {
    const res = await fetch(`${API_BASE}/reports/macro/latest`)
    if (res.ok) return res.json()
  } catch {
    // fallthrough to static JSON
  }
  try {
    const res = await fetch('/macro-report.json')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
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
