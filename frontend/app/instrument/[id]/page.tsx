"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ds/Avatar";
import { Button } from "@/components/ds/Button";
import { Chip } from "@/components/ds/Chip";
import { useAddToWatchlist, useDigest, useRemoveFromWatchlist, useWatchlist } from "@/lib/hooks";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

export default function InstrumentDigestPage({ params }: { params: { id: string } }) {
  const instrumentId = decodeURIComponent(params.id);
  const router = useRouter();
  const { data, isLoading, isError } = useDigest(instrumentId);
  const { data: watchlist } = useWatchlist();
  const addMutation = useAddToWatchlist();
  const removeMutation = useRemoveFromWatchlist();

  const isWatched = (watchlist ?? []).some((w) => w.instrument_id === instrumentId);

  if (isLoading) return <p style={{ color: "var(--text-tertiary)" }}>Loading digest…</p>;
  if (isError || !data) return <p style={{ color: "var(--text-negative)" }}>Couldn't load this instrument's digest.</p>;

  const positive = (data.price_delta_pct ?? 0) >= 0;
  const narrativeBg = data.price_delta_pct === null ? "var(--surface-sunken)" : positive ? "var(--green-50)" : "var(--red-50)";
  const narrativeColor = data.price_delta_pct === null ? "var(--text-secondary)" : positive ? "var(--text-positive)" : "var(--text-negative)";

  const ratioStats = Object.entries(data.ratio_deltas).map(([key, value]) => (
    <Stat key={key} label={key} value={`${(value * 100).toFixed(2)}%`} />
  ));

  return (
    <div style={{ fontFamily: "var(--font-body)", background: "var(--surface-page)", maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <span onClick={() => router.back()} style={{ cursor: "pointer", fontSize: 18 }}>
          ←
        </span>
        <Avatar label={instrumentId} size="sm" shape="square" />
        <span style={{ fontWeight: 500, fontSize: 18, fontFamily: "var(--font-display)" }}>{instrumentId}</span>
        <div style={{ flex: 1 }} />
        {data.significance[0] && <Chip>{data.significance[0].category}</Chip>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1.1fr_0.9fr] gap-5 md:gap-9">
        <div>
          {data.price !== null && (
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontWeight: 400, fontSize: 30 }}>₹{data.price.toFixed(2)}</span>
              {data.price_delta_pct !== null && (
                <span style={{ fontSize: 15, color: positive ? "var(--text-positive)" : "var(--text-negative)" }}>
                  {positive ? "+" : ""}
                  {(data.price_delta_pct * 100).toFixed(2)}%
                </span>
              )}
            </div>
          )}

          <div style={{ marginTop: 14, padding: 16, borderRadius: "var(--radius-md)", background: narrativeBg, display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: narrativeColor }}>Since you last checked</span>
            <span style={{ fontSize: 14, color: "var(--ink-2)" }}>{data.narrative}</span>
          </div>

          {(data.price_delta_pct !== null || data.volume_delta_pct !== null || ratioStats.length > 0) && (
            <div className="grid grid-cols-2 sm:grid-cols-4" style={{ gap: 16, marginTop: 20 }}>
              {data.price_delta_pct !== null && <Stat label="Price change" value={`${(data.price_delta_pct * 100).toFixed(2)}%`} />}
              {data.volume_delta_pct !== null && <Stat label="Volume change" value={`${(data.volume_delta_pct * 100).toFixed(2)}%`} />}
              {ratioStats}
            </div>
          )}

          {/* Neutral actions in place of the design's Buy/Sell pair — see
              the phase's flagged conflict with docs/SOURCE_OF_TRUTH.md's
              ban on order-execution/buy-sell language. Both tie into
              features this project actually has (watchlist, alerts). */}
          <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
            <Button
              variant={isWatched ? "outline" : "primary"}
              size="lg"
              fullWidth
              onClick={() => (isWatched ? removeMutation.mutate(instrumentId) : addMutation.mutate(instrumentId))}
            >
              {isWatched ? "Remove from watchlist" : "Add to watchlist"}
            </Button>
            <Link href={`/alerts?instrument=${encodeURIComponent(instrumentId)}`} style={{ flex: 1, textDecoration: "none" }}>
              <Button variant="secondary" size="lg" fullWidth>
                Set alert
              </Button>
            </Link>
          </div>
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <span style={{ fontWeight: 500, fontSize: 16 }}>News</span>
          </div>
          {data.news.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--text-tertiary)" }}>No related news in the relevant window.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data.news.map((item) => (
                <a
                  key={item.url}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ padding: 14, borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-card-border)", display: "flex", flexDirection: "column", gap: 5, textDecoration: "none", color: "inherit" }}
                >
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{item.title}</span>
                  <div style={{ display: "flex", gap: 6, fontSize: 12, color: "var(--text-tertiary)" }}>
                    <span>{item.source}</span>
                    <span>·</span>
                    <span>{new Date(item.published_at).toLocaleDateString()}</span>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
