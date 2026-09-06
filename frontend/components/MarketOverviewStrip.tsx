"use client";

import { Sparkline } from "./ds/Sparkline";
import { glassCard } from "./ds/glass";
import type { MarketOverviewEntry } from "@/lib/api";
import { useMarketOverview, useSparkline } from "@/lib/hooks";

const LABELS: Record<string, string> = {
  "^NSEI": "NIFTY 50",
  "^BSESN": "SENSEX",
  "USDINR=X": "USD/INR",
};

// Hero cards get a distinct treatment from ordinary list rows (watchlist
// items, news cards): a colored top accent tied to that index's own trend,
// a larger price digit, and an embedded sparkline — these are the "top of
// the app" headline numbers, not another row in a list.
function OverviewCard({ entry }: { entry: MarketOverviewEntry }) {
  const { data: sparkline } = useSparkline(entry.instrument_id);
  const positive = (entry.price_delta_pct ?? 0) >= 0;
  const accent = entry.price_delta_pct === null ? "var(--border-default)" : positive ? "var(--text-positive)" : "var(--text-negative)";

  return (
    <div
      style={{
        padding: "16px 18px",
        borderRadius: "var(--radius-lg)",
        borderTop: `3px solid ${accent}`,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        ...glassCard,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: "var(--text-label)", fontWeight: 700, color: "var(--text-tertiary)", letterSpacing: "0.3px" }}>
            {LABELS[entry.instrument_id] ?? entry.instrument_id}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 6 }}>
            <span style={{ fontSize: "var(--text-price)", fontWeight: 800, fontFamily: "var(--font-display)" }}>
              {entry.price !== null ? entry.price.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
            </span>
            {entry.price_delta_pct !== null && (
              <span style={{ fontSize: 13, fontWeight: 600, color: accent }}>
                {positive ? "+" : ""}
                {(entry.price_delta_pct * 100).toFixed(2)}%
              </span>
            )}
          </div>
        </div>
        {sparkline && sparkline.closes.length > 1 && <Sparkline closes={sparkline.closes} width={64} height={28} />}
      </div>
    </div>
  );
}

export function MarketOverviewStrip() {
  const { data } = useMarketOverview();
  if (!data || data.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: 12, marginBottom: 24 }}>
      {data.map((entry) => (
        <OverviewCard key={entry.instrument_id} entry={entry} />
      ))}
    </div>
  );
}
