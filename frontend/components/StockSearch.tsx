"use client";

import Link from "next/link";
import { useState } from "react";
import { glassCard } from "./ds/glass";
import { useAddToWatchlist, useInstruments, useWatchlist } from "@/lib/hooks";

export function StockSearch({ placeholder = "Search stocks, ETFs, mutual funds…" }: { placeholder?: string }) {
  const { data: instruments } = useInstruments();
  const { data: watchlist } = useWatchlist();
  const addMutation = useAddToWatchlist();
  const [query, setQuery] = useState("");

  const watchedIds = new Set((watchlist ?? []).map((w) => w.instrument_id));
  const matches =
    query.trim() === ""
      ? []
      : (instruments ?? []).filter((i) => i.id.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8);

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", borderRadius: "var(--radius-lg)", ...glassCard }}>
        <span style={{ color: "var(--text-tertiary)", fontSize: 16 }}>⌕</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
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
            <div key={i.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px", fontSize: 14 }}>
              <Link href={`/instrument/${encodeURIComponent(i.id)}`} onClick={() => setQuery("")} style={{ flex: 1, textDecoration: "none", color: "inherit" }}>
                <span style={{ fontWeight: 500 }}>{i.id}</span> <span style={{ color: "var(--text-tertiary)" }}>{i.sector ?? i.type}</span>
              </Link>
              {!watchedIds.has(i.id) && (
                <button
                  onClick={() => addMutation.mutate(i.id)}
                  style={{ border: "none", background: "var(--surface-chip)", borderRadius: 12, padding: "4px 10px", cursor: "pointer", fontSize: 13, flexShrink: 0 }}
                >
                  + Watch
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
