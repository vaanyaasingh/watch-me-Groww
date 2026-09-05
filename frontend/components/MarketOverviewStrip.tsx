"use client";

import { glassCard } from "./ds/glass";
import { useMarketOverview } from "@/lib/hooks";

const LABELS: Record<string, string> = {
  "^NSEI": "NIFTY 50",
  "^BSESN": "SENSEX",
  "USDINR=X": "USD/INR",
};

export function MarketOverviewStrip() {
  const { data } = useMarketOverview();
  if (!data || data.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: 10, marginBottom: 20 }}>
      {data.map((entry) => (
        <div key={entry.instrument_id} style={{ padding: "14px 18px", borderRadius: "var(--radius-md)", ...glassCard }}>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{LABELS[entry.instrument_id] ?? entry.instrument_id}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 20, fontWeight: 500 }}>
              {entry.price !== null ? entry.price.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
            </span>
            {entry.price_delta_pct !== null && (
              <span style={{ fontSize: 13, color: entry.price_delta_pct >= 0 ? "var(--text-positive)" : "var(--text-negative)" }}>
                {entry.price_delta_pct >= 0 ? "+" : ""}
                {(entry.price_delta_pct * 100).toFixed(2)}%
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
