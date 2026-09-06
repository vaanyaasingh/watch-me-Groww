// Thin fetch wrapper over the FastAPI backend (backend/app/api.py). No
// route handler is ever called directly from a component — every screen
// goes through the React Query hooks in lib/hooks.ts, which call the
// functions here, so the API base URL and error handling live in one place.

import { getIdToken } from "./auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getIdToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${options?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export type Instrument = {
  id: string;
  type: "equity" | "etf" | "mf";
  exchange: string | null;
  sector: string | null;
};

export type WatchlistEntry = {
  instrument_id: string;
  type: string | null;
  sector: string | null;
  price: number | null;
  status: string | null;
  last_checked_at: string | null;
  price_delta_pct: number | null;
};

export type SignificanceEntry = {
  category: string;
  detail: string | null;
  score: number;
};

// "live" | "stale" | "market_closed" — computed at request time by
// backend/app/staleness.py, not the raw ingestion-time DB value.
export type DisplayStatus = "live" | "stale" | "market_closed" | null;

export type AttentionFeedEntry = {
  instrument_id: string;
  sector: string | null;
  price_delta_pct: number;
  after_price: number;
  rank_score: number;
  significance: SignificanceEntry[];
  status: DisplayStatus;
  last_checked_at: string | null;
};

export type AttentionFeed = {
  top: AttentionFeedEntry[];
  collapsed: AttentionFeedEntry[];
};

export type NewsEntry = {
  title: string;
  source: string;
  url: string;
  published_at: string;
};

export type ExchangeReconciliation = {
  chosen_exchange: string;
  chosen_price: number;
  nse_price: number;
  bse_price: number;
  discrepancy_pct: number;
  disagreement: boolean;
};

export type Digest = {
  instrument_id: string;
  narrative: string;
  price: number | null;
  price_delta_pct: number | null;
  volume_delta_pct: number | null;
  ratio_deltas: Record<string, number>;
  significance: SignificanceEntry[];
  news: NewsEntry[];
  status: DisplayStatus;
  last_checked_at: string | null;
  exchange_reconciliation: ExchangeReconciliation | null;
};

export type Alert = {
  id: number;
  instrument_id: string;
  condition: { target_price: number | null; notify_on_significant_change: boolean };
  status: string;
};

export type SubscriptionWindowEntry = {
  instrument_id: string;
  type: string | null;
  status: "open" | "closing_soon" | "closed" | string;
  last_changed_at: string;
  // Populated once a real ingestion run has resolved+searched this scheme
  // (see backend/app/subscription_tracker.py) — null for a row that's
  // still just the seed-time placeholder.
  scheme_name: string | null;
  evidence: string | null;
};

export type MarketOverviewEntry = {
  instrument_id: string;
  type: string | null;
  price: number | null;
  price_delta_pct: number | null;
  status: DisplayStatus;
  last_checked_at: string | null;
};

export type Me = {
  email: string;
  watchlist_count: number;
};

export type SparklinePoint = { date: string; close: number };

export type Sparkline = {
  instrument_id: string;
  closes: SparklinePoint[];
};

export const api = {
  listInstruments: () => request<Instrument[]>("/api/instruments"),

  getWatchlist: () => request<WatchlistEntry[]>("/api/watchlist"),
  addToWatchlist: (instrument_id: string) =>
    request<{ instrument_id: string }>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ instrument_id }),
    }),
  removeFromWatchlist: (instrumentId: string) =>
    request<void>(`/api/watchlist/${encodeURIComponent(instrumentId)}`, { method: "DELETE" }),

  getAttentionFeed: () => request<AttentionFeed>("/api/attention-feed"),

  getDigest: (instrumentId: string) =>
    request<Digest>(`/api/instruments/${encodeURIComponent(instrumentId)}/digest`),

  getAlerts: () => request<Alert[]>("/api/alerts"),
  createAlert: (payload: { instrument_id: string; target_price?: number | null; notify_on_significant_change: boolean }) =>
    request<Alert>("/api/alerts", { method: "POST", body: JSON.stringify(payload) }),
  deleteAlert: (id: number) => request<void>(`/api/alerts/${id}`, { method: "DELETE" }),

  getSubscriptionWindows: () => request<SubscriptionWindowEntry[]>("/api/subscription-windows"),

  getMarketOverview: () => request<MarketOverviewEntry[]>("/api/market-overview"),
  getMe: () => request<Me>("/api/me"),

  getSparkline: (instrumentId: string) =>
    request<Sparkline>(`/api/instruments/${encodeURIComponent(instrumentId)}/sparkline`),
};
