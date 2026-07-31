export type TxKind = "BUY" | "SELL" | "DEPOSIT" | "WITHDRAW" | "DIVIDEND" | "FEE";

export interface PortfolioSummary {
  id: number;
  name: string;
  base_currency: string;
}

export interface Position {
  asset_canonical_id: string;
  display_symbol: string;
  market: string;
  quantity: string;
  avg_cost: string;
  quote_currency: string;
  last_price: string | null;
  last_price_source: string | null;
  last_price_time: string | null;
  market_value_ccy: string | null;
  market_value_base: string | null;
  unrealized_pnl_ccy: string | null;
  unrealized_pnl_base: string | null;
  realized_pnl_ccy: string;
}

export interface PortfolioDetail {
  id: number;
  name: string;
  base_currency: string;
  as_of: string;
  cash_by_currency: Record<string, string>;
  cash_base: string;
  positions_value_base: string;
  equity_base: string;
  realized_pnl_base: string;
  unrealized_pnl_base: string;
  positions: Position[];
  fx_used: Record<string, string>;
  warnings: string[];
}

export interface PortfolioRisk {
  portfolio_id: number;
  base_currency: string;
  as_of: string;
  total_equity_base: number;
  allocation_by_asset: Record<string, number>;
  allocation_by_market: Record<string, number>;
  cash_weight: number;
  hhi_asset: number;
  top_holding_weight: number;
  n_holdings: number;
  lookback_days: number;
  volatility_annualized: number | null;
  max_drawdown: number | null;
  var_95_1d: number | null;
  var_99_1d: number | null;
  correlation_matrix: Record<string, Record<string, number>>;
  stress_scenarios: Record<string, number>;
  warnings: string[];
}
