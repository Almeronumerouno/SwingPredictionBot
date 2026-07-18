export interface Gainer {
  kode: string;
  nama: string;
  harga_sekarang: number;
  perubahan_persen: number;
  volume: number;
  frekuensi: number;
  rata_rata_volume_20: number;
  volume_ratio: number;
  kategori: string;
}

export interface ScoreAnalysis {
  trend_ema: number;
  trend_ma: number;
  volume_ratio: number;
  volume_trend: number;
  volatilitas: number;
  momentum: number;
  wsp: number;
  atr_band: number;
  total: number;
}

export interface TradingResult {
  entry: string;
  exit: string;
  entry_price: number;
  exit_price: number;
  pnl_persen: number;
  holding_days: number;
}

export interface HistoryStats {
  total_trades: number;
  win_rate: number;
  avg_pnl: number;
  avg_holding_days: number;
  max_win: number;
  max_loss: number;
  results: TradingResult[];
}

export interface AnalisisResponse {
  kode: string;
  nama: string;
  harga: number;
  support: number;
  resist: number;
  score: ScoreAnalysis;
  rekomendasi: string;
  trading_plan: {
    entry_zone: string;
    stop_loss: number;
    target_1: number;
    target_2: number;
    risk_reward: string;
    modal_dibutuhkan: number;
  };
  history: HistoryStats;
}

export interface PriceHistoryResponse {
  kode: string;
  days: number;
  data: Candle[];
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ErrorResponse {
  detail: string;
}
