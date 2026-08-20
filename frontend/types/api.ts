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
  gorengan_score: number | null
  gorengan_level: string | null
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
  risk_per_trade_pct?: number | null
  note: string | null
}

export interface RawIndicators {
  rsi: number | null
  mfi: number | null
  atr: number | null
  adx: number | null
  plus_di: number | null
  minus_di: number | null
  ema_fast: number | null
  ema_slow: number | null
  rvol: number | null
  support: number | null
  resistance: number | null
  fibonacci: Record<string, number> | null
  candlestick_patterns: string[]
  pattern_candles?: { open: number; high: number; low: number; close: number }[]
}

export interface GorenganFactors {
  historical_pump_dump_risk: number
  liquidity_risk: number
  market_cap_risk: number
  active_pump: number
  mid_momentum: number
  distribution_risk: number
  turnover_gaps: number
}

export interface GorenganScannerEntry {
  code: string
  name: string
  close: number
  pct_change: number
  volume: number
  value: number
  frequency: number
  gorengan_score: number
  gorengan_level: string
  factors: GorenganFactors
  warnings: string[]
}

export interface GorenganScannerResponse {
  scraped_at: string
  date: string
  count: number
  data: GorenganScannerEntry[]
}

export interface GorenganAnalysis {
  score: number
  level: string
  factors: GorenganFactors
  warnings: string[]
  explanation: string
}

export interface FundamentalFlag {
  flag: string
  reason: string
}

export interface FundamentalCoverage {
  observed: number
  assumed: number
  unknown: number
  required: number
  ratio: number
}

export interface FundamentalContext {
  data_quality: string | null
  coverage: FundamentalCoverage | null
  context: {
    market_cap?: number | null
    market_cap_idr_b?: number | null
    note?: string
  } | null
  fetch_errors: string[]
}

export interface AnalisisResponse {
  kode: string
  nama: string
  harga: number
  last_updated: string
  fetched_at?: string
  data_delayed?: boolean
  score: ScoreResponse
  trade_plan: TradePlanResponse | null
  raw_indicators: RawIndicators | null
  capital_used: number
  gorengan: GorenganAnalysis | null
  fundamental_status?: string
  fundamental_flags?: FundamentalFlag[]
  fundamental_meta?: FundamentalContext
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

export interface RecoveryProbability {
  horizon_days: number
  p_hit: number
  ci_low: number | null
  ci_high: number | null
}

export interface RecoveryEmpirical {
  horizon_days: number
  n_events: number
  n_recovered: number
  rate: number | null
}

export interface RecoveryGbm {
  mu_daily: number
  sigma_daily: number
  mu_annual: number
  sigma_annual: number
  p_hit_ever: number
  probabilities: RecoveryProbability[]
}

export interface RecoveryModel {
  kind: string
  target: string
  target_desc: string
  dd_fraction: number | null
  prior_peak: number | null
  probabilities: RecoveryProbability[] | null
  params_version: string
}

export interface RecoveryExitPlan {
  target: number
  time_stop_days: number
  stop_loss: number
  note: string
}

export interface RecoveryVsLookback {
  days: number
  label: string
  ref_price: number
  distance_pct: number
  status: "above" | "below"
  threshold_pct?: number | null
}

export interface RecoveryAccumulation {
  valid: boolean
  ready_to_fly: boolean
  k_heavy: number
  window_days: number
  density_pct: number | null
  rvol: number | null
  max_rvol: number | null
  ara_date: string | null
  ara_ref_price: number | null
  prev_ara_date?: string | null
  prev_ara_ref_price?: number | null
  days_since_prev_ara?: number | null
  double_ara?: boolean
  gates?: { below?: boolean; density?: boolean; min_heavy?: boolean; above_ma?: boolean; liquidity?: boolean } | null
  sma20: number | null
  state_ma20: "above" | "breakout" | "below" | null
  distance_pct: number | null
  net_dist_heavy?: number | null
  acc_density?: number | null
  post_ara_decay?: number | null
  adv_vol_20?: number | null
  adv_val_20?: number | null
  liquidity_ok?: boolean
  liquidity_prima?: boolean
  note: string | null
  warning: string | null
  reason: string | null
}

export interface RecoveryResponse {
  kode: string
  nama: string
  valid: boolean
  harga: number | null
  ref_price: number | null
  ref_days: number | null
  last_updated: string
  distance_pct: number | null
  drop_pct: number
  drop_source: "auto" | "manual"
  in_setup: boolean
  gbm: RecoveryGbm | null
  model: RecoveryModel | null
  signal_basis: string | null
  empirical: RecoveryEmpirical[]
  signal: string
  signal_reason: string
  exit_plan: RecoveryExitPlan | null
  vs_lookbacks: RecoveryVsLookback[]
  accumulation: RecoveryAccumulation | null
}

export interface Candle {
  time: string
  open: number
  high: number
  low: number
  close: number
}

export interface ReadyToFlyEntry {
  code: string
  name: string
  close: number
  pct_change: number
  status: "ready" | "almost"
  density_pct: number | null
  k_heavy: number
  window_days: number
  ara_date: string | null
  ara_ref_price: number | null
  distance_pct: number | null
  net_dist: number | null
  net_dist_heavy?: number | null
  acc_density?: number | null
  post_ara_decay?: number | null
  strength?: number | null
  adv_vol_20?: number | null
  adv_val_20?: number | null
  liquidity_ok?: boolean
  liquidity_prima?: boolean
  sma_gap_pct: number | null
  sma20: number | null
  state_ma20: string | null
  max_rvol: number | null
  gates: { below?: boolean; density?: boolean; min_heavy?: boolean; above_ma?: boolean; liquidity?: boolean; vcp?: boolean; dryup?: boolean } | null
  note: string | null
  reason: string | null
  post_ara_volume?: number | null
  post_ara_value?: number | null
  vcp_ratio?: number | null
  dryup_ratio?: number | null
  vcp_ok?: boolean
  dryup_ok?: boolean
}

export interface ReadyToFlyScannerResponse {
  scraped_at: string
  date: string
  count_ready: number
  count_almost: number
  data: ReadyToFlyEntry[]
}
