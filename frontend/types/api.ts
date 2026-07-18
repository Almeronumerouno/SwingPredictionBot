export interface GainerEntry {
  code: string
  name: string
  close: number
  pct_change: number
  volume: number
  value: number
  frequency: number
  foreign_buy: number
  foreign_sell: number
  swing_score: number | null
  recommendation: string | null
}

export interface GainersResponse {
  scraped_at: string
  date: string
  count: number
  data: GainerEntry[]
}

export interface ScoreResponse {
  valid: boolean
  swing_score: number | null
  components: {
    trend: number
    momentum: number
    volume: number
    price_action: number
  } | null
  recommendation: string | null
  confidence: string | null
  risk_level: string | null
}

export interface TradePlanResponse {
  direction: string
  entry: number
  stop_loss: number
  take_profit: number
  shares: number
  lots: number
  risk_reward_ratio: number | null
}

export interface AnalisisResponse {
  kode: string
  nama: string
  harga: number
  last_updated: string
  score: ScoreResponse
  trade_plan: TradePlanResponse | null
  capital_used: number
}

export interface HistoryBar {
  date: string
  close: number
  open: number
  high: number
  low: number
  volume: number
}

export interface HistoryResponse {
  kode: string
  bars: HistoryBar[]
}

export interface Candle {
  time: string
  open: number
  high: number
  low: number
  close: number
}
