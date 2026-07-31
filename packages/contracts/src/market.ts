export interface MarketStatus {
  market: string;
  calendar: string;
  timezone: string;
  is_open: boolean;
  now_utc: string;
  next_open_utc: string | null;
  next_close_utc: string | null;
  state: "OPEN" | "CLOSED";
}

export interface ProviderStatus {
  slug: string;
  kind: string;
  status: "ok" | "degraded" | "down" | "unknown" | "missing_credentials";
  message: string;
  markets: string[];
  is_selected_for: string[];
}
