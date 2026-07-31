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

export interface Signal {
  asset_id: string;
  as_of: string; // ISO
  data_fresh_seconds: number;
  horizon: "1D" | "5D" | "20D";
  classification: SignalClassification;
  score: number; // -100..100
  confidence: number; // 0..1 (calibrated)
  risk: RiskClass;
  expected_holding_days: number;
  entry_zone?: [string, string];
  invalidation?: string;
  take_profit?: string[];
  positive_factors: SignalFactor[];
  negative_factors: SignalFactor[];
  contradictions: string[];
  liquidity_warnings: string[];
  data_quality_score: number; // 0..1
  regime: string;
  backtest?: BacktestSummary;
  strategy_version: string;
  data_version: string;
  generated_at: string;
  disclaimer: string;
}
