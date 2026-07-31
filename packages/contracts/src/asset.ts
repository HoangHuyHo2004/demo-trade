export type AssetType = "EQUITY" | "ETF" | "CRYPTO" | "INDEX";
export type MarketCode = "US" | "VN" | "COINBASE" | "KRAKEN" | "BINANCE";

export interface Asset {
  id: number;
  canonical_id: string; // e.g. "EQUITY:US:NASDAQ:AAPL" | "CRYPTO:COINBASE:BTC-USD"
  asset_type: AssetType;
  market: MarketCode;
  exchange_code: string;
  symbol: string;
  display_symbol: string;
  name: string;
  quote_currency: string;
  market_timezone: string;
  calendar: string;
  is_active: boolean;
  is_benchmark: boolean;
}

export type BarInterval = "1m" | "15m" | "1h" | "1d" | "1w" | "1mo";

export interface Bar {
  t: string; // ISO datetime, UTC
  o: string; // Decimal-as-string
  h: string;
  l: string;
  c: string;
  v: string;
}

export interface BarsResponse {
  asset_id: string;
  interval: BarInterval;
  source: string;
  bars: Bar[];
}

export type MarketState = "OPEN" | "CLOSED" | "PRE" | "POST" | "UNKNOWN";

export interface Quote {
  asset_id: string;
  price: string;
  currency: string;
  event_time: string;
  source: string;
  is_stale: boolean;
  market_state: MarketState;
}
