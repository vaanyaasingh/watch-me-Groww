const STATUS_LABEL: Record<string, string> = {
  live: "Live",
  stale: "Feed stuck",
  market_closed: "Market closed",
};

const STATUS_COLOR: Record<string, string> = {
  live: "var(--status-open)",
  stale: "var(--attention-high)",
  market_closed: "var(--text-tertiary)",
};

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** Surfaces Phase 7's stale-vs-closed distinction (app/staleness.py) and
 * the "last seen" timestamp — a feed that's merely old because NSE is
 * shut reads differently from one that's stuck open-market. */
export function Freshness({ status, lastCheckedAt }: { status: string | null; lastCheckedAt: string | null }) {
  if (!status || !lastCheckedAt) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--text-tertiary)" }}>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: STATUS_COLOR[status] ?? "var(--text-tertiary)",
          flexShrink: 0,
        }}
      />
      {STATUS_LABEL[status] ?? status} · {relativeTime(lastCheckedAt)}
    </span>
  );
}
