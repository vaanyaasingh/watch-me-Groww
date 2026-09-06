"use client";

import { useState } from "react";
import Link from "next/link";
import { Avatar } from "@/components/ds/Avatar";
import { Badge } from "@/components/ds/Badge";
import { Freshness } from "@/components/ds/Freshness";
import { Sparkline } from "@/components/ds/Sparkline";
import { glassCard } from "@/components/ds/glass";
import { MarketOverviewStrip } from "@/components/MarketOverviewStrip";
import { StockSearch } from "@/components/StockSearch";
import type { AttentionFeedEntry } from "@/lib/api";
import { useAttentionFeed, useSparkline } from "@/lib/hooks";

// Named per the Phase 6 brief ("make it a constant, not hardcoded
// inline") — the backend already truncates to this same number
// (app/api.py's ATTENTION_FEED_TOP_N), this just labels what arrived.
const ATTENTION_FEED_TOP_N = 5;

function attentionLevel(rankScore: number): "high" | "medium" | "low" {
  if (rankScore >= 5) return "high";
  if (rankScore >= 2) return "medium";
  return "low";
}

const LEVEL_LABEL = { high: "High", medium: "Medium", low: "Low" } as const;

function summaryFor(entry: AttentionFeedEntry): string {
  const direction = entry.price_delta_pct >= 0 ? "Up" : "Down";
  const pct = Math.abs(entry.price_delta_pct * 100).toFixed(1);
  const reason = entry.significance[0]?.category;
  const reasonLabel =
    reason === "statistical" ? "statistical deviation" : reason === "threshold" ? "threshold crossed" : reason === "event" ? "flagged event" : null;
  return reasonLabel ? `${direction} ${pct}% — ${reasonLabel}` : `${direction} ${pct}% — within normal range`;
}

function FeedCard({ entry }: { entry: AttentionFeedEntry }) {
  const level = attentionLevel(entry.rank_score);
  const positive = entry.price_delta_pct >= 0;
  const { data: sparkline } = useSparkline(entry.instrument_id);
  return (
    <Link
      href={`/instrument/${encodeURIComponent(entry.instrument_id)}`}
      style={{
        display: "flex",
        gap: 14,
        padding: "16px 18px",
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        borderLeft: `4px solid var(--attention-${level})`,
        textDecoration: "none",
        color: "inherit",
        transition: "background .15s ease",
        ...glassCard,
      }}
    >
      <Avatar label={entry.instrument_id} size="lg" shape="square" alt={entry.instrument_id} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 500, fontSize: 16 }}>{entry.instrument_id}</span>
          <Badge kind={`attention-${level}`}>{LEVEL_LABEL[level]}</Badge>
        </div>
        {entry.sector && <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{entry.sector}</span>}
        <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>{summaryFor(entry)}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 500, fontSize: 14 }}>₹{entry.after_price.toFixed(2)}</span>
          <span style={{ fontSize: 13, color: positive ? "var(--text-positive)" : "var(--text-negative)" }}>
            {positive ? "+" : ""}
            {(entry.price_delta_pct * 100).toFixed(2)}%
          </span>
          <Freshness status={entry.status} lastCheckedAt={entry.last_checked_at} />
        </div>
      </div>
      {sparkline && sparkline.closes.length > 1 && (
        <div style={{ alignSelf: "center", flexShrink: 0 }}>
          <Sparkline closes={sparkline.closes} />
        </div>
      )}
    </Link>
  );
}

export default function AttentionFeedPage() {
  const { data, isLoading, isError } = useAttentionFeed();
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 920, margin: "0 auto" }}>
      <MarketOverviewStrip />

      <div style={{ marginBottom: 24 }}>
        <StockSearch />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <span style={{ fontWeight: 500, fontSize: 18, fontFamily: "var(--font-display)" }}>Attention</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>Ranked by significance, not alphabetically</span>
      </div>

      {isLoading && <p style={{ color: "var(--text-tertiary)" }}>Loading your attention feed…</p>}
      {isError && <p style={{ color: "var(--text-negative)" }}>Couldn't load the attention feed.</p>}

      {data && data.top.length === 0 && data.collapsed.length === 0 && (
        <p style={{ color: "var(--text-tertiary)", fontSize: 14 }}>
          Nothing to show yet — add instruments to your{" "}
          <Link href="/watchlist" style={{ color: "var(--accent-info)" }}>
            watchlist
          </Link>{" "}
          and run an ingestion cycle.
        </p>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 12 }}>
          {data.top.slice(0, ATTENTION_FEED_TOP_N).map((entry) => (
            <FeedCard key={entry.instrument_id} entry={entry} />
          ))}
        </div>
      )}

      {data && data.collapsed.length > 0 && (
        <div style={{ marginTop: 28, borderRadius: "var(--radius-md)", padding: 4, ...glassCard }}>
          <div
            onClick={() => setExpanded(!expanded)}
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 14px", cursor: "pointer", opacity: 0.7 }}
          >
            <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>No meaningful change ({data.collapsed.length})</span>
            <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{expanded ? "Hide" : "Show"}</span>
          </div>
          {expanded && (
            <div style={{ display: "flex", flexDirection: "column", padding: "0 14px 8px" }}>
              {data.collapsed.map((entry) => (
                <div
                  key={entry.instrument_id}
                  style={{ display: "flex", justifyContent: "space-between", padding: "10px 4px", borderBottom: "1px solid rgba(0,0,0,0.06)", fontSize: 13 }}
                >
                  <span>{entry.instrument_id}</span>
                  <span style={{ color: "var(--text-tertiary)" }}>
                    {entry.price_delta_pct >= 0 ? "+" : ""}
                    {(entry.price_delta_pct * 100).toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
