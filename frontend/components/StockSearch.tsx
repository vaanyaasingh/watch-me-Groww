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
  const [focused, setFocused] = useState(false);

  const watchedIds = new Set((watchlist ?? []).map((w) => w.instrument_id));
  const matches =
    query.trim() === ""
      ? []
      : (instruments ?? []).filter((i) => i.id.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8);

  return (
    <div style={{ position: "relative" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 18px",
          borderRadius: "var(--radius-lg)",
          transition: "box-shadow .15s ease",
          ...glassCard,
          ...(focused ? { boxShadow: "0 0 0 2px var(--accent-info), var(--glass-shadow)" } : {}),
        }}
      >
        <span style={{ color: "var(--text-tertiary)", fontSize: 16 }}>⌕</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          style={{ border: "none", outline: "none", background: "transparent", flex: 1, fontFamily: "var(--font-body)", fontSize: 15, color: "var(--text-primary)" }}
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
                  style={{
                    border: "none",
                    background: "var(--accent-primary)",
                    color: "var(--text-inverse)",
                    borderRadius: 12,
                    padding: "5px 12px",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
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
