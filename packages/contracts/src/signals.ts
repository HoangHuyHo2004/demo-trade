/**
 * Signal payload shape (Phase 3 will implement the producer; the shape is
 * frozen here so the frontend can build against it and Phase 3 fills it in).
 */
export type SignalClassification =
  | "STRONG_BULLISH"
  | "BULLISH"
  | "NEUTRAL"
  | "BEARISH"
  | "STRONG_BEARISH"
  | "AVOID_HIGH_RISK"
  | "INSUFFICIENT_DATA";

export type RiskClass = "LOW" | "MODERATE" | "HIGH" | "SEVERE";

export interface SignalFactor {
  code: string;
  label: string;
  contribution: number; // -1..1
  detail?: string;
}

export interface BacktestSummary {
  total_return: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  hit_rate: number;
  trades: number;
  costs_included: boolean;
}

export type DataFreshness = "CURRENT" | "STALE" | "UNAVAILABLE";

export interface Signal {
  asset_id: string;
  as_of: string; // ISO
  data_fresh_seconds: number;
  // Spec §9 canonical fields (Phase 5.2)
  model_version: string;
  data_source: string;
  data_freshness: DataFreshness;
  expected_holding_period: string;
  warnings: string[];
  // Original fields (kept as aliases so nothing breaks)
  horizon: "1D" | "5D" | "20D";
  classification: SignalClassification;
  score: number; // -100..100
  confidence: number; // 0..1 (calibrated)
  risk: RiskClass;
  expected_holding_days: number;
  entry_zone: [string, string] | null;
  invalidation: string | null;
  take_profit: string[] | null;
  positive_factors: SignalFactor[];
  negative_factors: SignalFactor[];
  contradictions: string[];
  liquidity_warnings: string[];
  data_quality_score: number; // 0..1
  regime: string;
  backtest?: BacktestSummary | null;
  strategy_version: string;   // alias of model_version
  data_version: string;
  generated_at: string;
  disclaimer: string;
}

export interface BacktestMetrics {
  total_return: number;
  cagr: number;
  volatility: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  calmar: number;
  win_rate: number;
  profit_factor: number | "inf";
  turnover: number;
  trades: number;
  avg_holding_bars: number;
  exposure: number;
  hit_rate: number;
  buy_hold_return: number;
  cash_return: number;
  sma_baseline_return: number;
  benchmark_return: number | null;
  bars_bull: number;
  bars_bear: number;
  bars_neutral: number;
  warnings?: string[];
}

export interface BacktestTrade {
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  bars_held: number;
  pnl_pct: number;
  cost_pct: number;
  reason: string;
}

export interface BacktestEquityPoint {
  t: string;
  strategy: number;
  buy_hold: number;
  in_position: boolean;
}

export interface BacktestResult {
  id: number;
  asset_id: number | string;
  horizon: "1D" | "5D" | "20D";
  interval: string;
  start_time: string;
  end_time: string;
  cost_bps: string;
  slippage_bps: string;
  params: Record<string, unknown>;
  metrics: BacktestMetrics;
  warnings?: string[];
  trades: BacktestTrade[];
  equity: BacktestEquityPoint[];
}
