"use client";

import { useState } from "react";
import Link from "next/link";
import { Avatar } from "@/components/ds/Avatar";
import { Freshness } from "@/components/ds/Freshness";
import { glassCard } from "@/components/ds/glass";
import { useAddToWatchlist, useInstruments, useRemoveFromWatchlist, useWatchlist } from "@/lib/hooks";

export default function WatchlistPage() {
  const { data: watchlist, isLoading } = useWatchlist();
  const { data: instruments } = useInstruments();
  const addMutation = useAddToWatchlist();
  const removeMutation = useRemoveFromWatchlist();
  const [query, setQuery] = useState("");

  const watchedIds = new Set((watchlist ?? []).map((w) => w.instrument_id));
  const matches =
    query.trim() === ""
      ? []
      : (instruments ?? [])
          .filter((i) => !watchedIds.has(i.id) && i.id.toLowerCase().includes(query.trim().toLowerCase()))
          .slice(0, 8);

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontWeight: 500, fontSize: 18, fontFamily: "var(--font-display)" }}>Watchlist</span>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{(watchlist ?? []).length} tracked</span>
      </div>

      <div style={{ position: "relative", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderRadius: "var(--radius-md)", ...glassCard }}>
          <span style={{ color: "var(--text-tertiary)" }}>⌕</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search to add a stock, MF or ETF"
            style={{ border: "none", outline: "none", background: "transparent", flex: 1, fontFamily: "var(--font-body)", fontSize: 15 }}
          />
        </div>
        {matches.length > 0 && (
          <div
            style={{
              position: "absolute",
              zIndex: 10,
              top: "100%",
              left: 0,
              right: 0,
              marginTop: 4,
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              ...glassCard,
            }}
          >
            {matches.map((i) => (
              <div
                key={i.id}
                onClick={() => {
                  addMutation.mutate(i.id);
                  setQuery("");
                }}
                style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", cursor: "pointer", fontSize: 14 }}
              >
                <span>{i.id}</span>
                <span style={{ color: "var(--text-tertiary)" }}>{i.sector ?? i.type}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {isLoading && <p style={{ color: "var(--text-tertiary)" }}>Loading watchlist…</p>}
      {watchlist && watchlist.length === 0 && <p style={{ color: "var(--text-tertiary)", fontSize: 14 }}>Your watchlist is empty — search above to add one.</p>}

      <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 10 }}>
        {(watchlist ?? []).map((item) => (
          <div
            key={item.instrument_id}
            style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: "var(--radius-md)", ...glassCard }}
          >
            <Link href={`/instrument/${encodeURIComponent(item.instrument_id)}`} style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0, textDecoration: "none", color: "inherit" }}>
              <Avatar label={item.instrument_id} size="sm" shape="square" />
              <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, gap: 2 }}>
                <span style={{ fontSize: 15, fontWeight: 400 }}>{item.instrument_id}</span>
                <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{item.sector ?? item.type}</span>
                <Freshness status={item.status} lastCheckedAt={item.last_checked_at} />
              </div>
            </Link>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>{item.price !== null ? `₹${item.price.toFixed(2)}` : "—"}</span>
              {item.price_delta_pct !== null && (
                <span style={{ fontSize: 12, color: item.price_delta_pct >= 0 ? "var(--text-positive)" : "var(--text-negative)" }}>
                  {item.price_delta_pct >= 0 ? "+" : ""}
                  {(item.price_delta_pct * 100).toFixed(2)}%
                </span>
              )}
            </div>
            <span
              onClick={() => removeMutation.mutate(item.instrument_id)}
              style={{ fontSize: 16, color: "var(--text-tertiary)", cursor: "pointer", marginLeft: 8 }}
              aria-label={`Remove ${item.instrument_id}`}
            >
              ✕
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
