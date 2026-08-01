export interface MLContributor {
  feature: string;
  value: number;
  contribution: number;
  description?: string;
}

export interface MLPrediction {
  asset_id: string;
  as_of: string;
  horizon: "1D" | "5D" | "20D";
  model_version: string;
  data_version: string;
  prob_positive: number | null;
  prob_negative: number | null;
  expected_return_median: number | null;
  expected_return_lower: number | null;
  expected_return_upper: number | null;
  expected_volatility: number | null;
  trend_continuation_probability: number | null;
  drawdown_risk: "LOW" | "MEDIUM" | "HIGH" | null;
  market_regime: string | null;
  confidence: number | null;
  ood_score: number | null;
  positive_contributors: MLContributor[];
  negative_contributors: MLContributor[];
  warnings: string[];
  shadow_only: boolean;
  disclaimer: string;
}

export interface MLInsufficient {
  asset_id: string;
  status: "INSUFFICIENT_DATA";
  detail: string;
}

export type MLPredictionResponse = MLPrediction | MLInsufficient;

export function isMLInsufficient(x: MLPredictionResponse): x is MLInsufficient {
  return (x as MLInsufficient).status === "INSUFFICIENT_DATA";
}
