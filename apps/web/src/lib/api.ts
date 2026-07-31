import { readRuntimeConfig } from "@demo-trade/config";
import type {
  AgentChatResponse,
  Asset,
  BacktestResult,
  BarsResponse,
  MarketStatus,
  PortfolioDetail,
  PortfolioRisk,
  PortfolioSummary,
  ProviderStatus,
  Quote,
  Signal,
  Watchlist
} from "@demo-trade/contracts";

const cfg = readRuntimeConfig(
  typeof process !== "undefined" ? (process.env as Record<string, string | undefined>) : {}
);

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${cfg.apiBaseUrl}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    credentials: "include",
    cache: "no-store"
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export const api = {
  searchAssets: (q: string) =>
    req<Asset[]>(`/api/v1/assets/search?q=${encodeURIComponent(q)}`),
  getAsset: (id: string) => req<Asset>(`/api/v1/assets/${encodeURIComponent(id)}`),
  getQuote: (id: string) => req<Quote>(`/api/v1/prices/${encodeURIComponent(id)}/quote`),
  getBars: (id: string, interval = "1d", lookback = 365) =>
    req<BarsResponse>(
      `/api/v1/prices/${encodeURIComponent(id)}/bars?interval=${interval}&lookback_days=${lookback}`
    ),
  marketStatus: () => req<MarketStatus[]>(`/api/v1/markets/status`),
  providersStatus: () => req<ProviderStatus[]>(`/api/v1/providers/status`),
  listWatchlists: () => req<Watchlist[]>(`/api/v1/watchlists`),
  createWatchlist: (name: string) =>
    req<Watchlist>(`/api/v1/watchlists`, { method: "POST", body: JSON.stringify({ name }) }),
  addWatchlistItem: (wlId: number, assetCanonicalId: string, note = "") =>
    req(`/api/v1/watchlists/${wlId}/items`, {
      method: "POST",
      body: JSON.stringify({ asset_canonical_id: assetCanonicalId, note })
    }),
  removeWatchlistItem: (wlId: number, itemId: number) =>
    req(`/api/v1/watchlists/${wlId}/items/${itemId}`, { method: "DELETE" }),
  getSignal: (id: string, horizon: "1D" | "5D" | "20D" = "5D") =>
    req<Signal>(
      `/api/v1/signals/${encodeURIComponent(id)}?horizon=${horizon}`
    ),
  runBacktest: (body: {
    asset_canonical_id: string;
    interval?: string;
    horizon: "1D" | "5D" | "20D";
    entry_threshold?: number;
    exit_threshold?: number;
    cost_bps?: number | null;
    slippage_bps?: number | null;
    start?: string | null;
    end?: string | null;
  }) =>
    req<BacktestResult>(`/api/v1/backtests`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  getBacktest: (id: number) => req<BacktestResult>(`/api/v1/backtests/${id}`),
  agentChat: (body: {
    prompt: string;
    asset_canonical_id?: string | null;
    max_tool_calls?: number;
  }) =>
    req<AgentChatResponse>(`/api/v1/agent/chat`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  listPortfolios: () => req<PortfolioSummary[]>(`/api/v1/portfolios`),
  createPortfolio: (name: string, base_currency = "USD") =>
    req<PortfolioSummary>(`/api/v1/portfolios`, {
      method: "POST",
      body: JSON.stringify({ name, base_currency })
    }),
  getPortfolio: (id: number) => req<PortfolioDetail>(`/api/v1/portfolios/${id}`),
  addTransaction: (id: number, body: {
    kind: string;
    asset_canonical_id?: string | null;
    quantity: string;
    price?: string;
    currency: string;
    fee?: string;
    executed_at?: string | null;
    note?: string;
  }) =>
    req(`/api/v1/portfolios/${id}/transactions`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  getPortfolioRisk: (id: number, lookback_days = 180) =>
    req<PortfolioRisk>(
      `/api/v1/portfolios/${id}/risk?lookback_days=${lookback_days}`
    ),
  getSettings: () => req<UserSettingsShape>(`/api/v1/settings`),
  patchSettings: (body: Partial<UserSettingsShape>) =>
    req<UserSettingsShape>(`/api/v1/settings`, {
      method: "PATCH",
      body: JSON.stringify(body)
    })
};

export interface UserSettingsShape {
  email: string;
  display_name: string;
  base_currency: string;
  locale: "en" | "vi";
  timezone: string;
  risk_display: "BOTH" | "LEVEL_ONLY" | "SCORE_ONLY";
  signal_horizon_default: "1D" | "5D" | "20D";
  theme: "light" | "dark" | "system";
  notifications_email: boolean;
}

export const runtime = cfg;
