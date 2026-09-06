"use client";

import { Avatar } from "@/components/ds/Avatar";
import { Badge } from "@/components/ds/Badge";
import { glassCard } from "@/components/ds/glass";
import type { SubscriptionWindowEntry } from "@/lib/api";
import { useSubscriptionWindows } from "@/lib/hooks";

const STATUS_LABEL: Record<string, string> = { open: "Open", closing_soon: "Closing soon", closed: "Closed" };
const STATUS_DOT: Record<string, string> = { open: "var(--status-open)", closing_soon: "var(--status-closing)", closed: "var(--status-closed)" };

function note(entry: SubscriptionWindowEntry): string {
  if (entry.status === "closed") return `Closed on ${new Date(entry.last_changed_at).toLocaleDateString()}`;
  if (entry.status === "closing_soon") return "Closing soon";
  return "Open — no closing date";
}

function Row({ entry }: { entry: SubscriptionWindowEntry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16, borderRadius: "var(--radius-md)", ...glassCard }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: STATUS_DOT[entry.status] ?? "var(--status-closed)" }} />
        <Avatar label={entry.instrument_id} size="md" shape="square" />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
          <span style={{ fontSize: 14.5, fontWeight: 700 }}>{entry.scheme_name ?? entry.instrument_id}</span>
          <span style={{ fontSize: 12, color: "var(--text-tertiary)", fontWeight: 600 }}>{note(entry)}</span>
        </div>
        <Badge kind={`status-${entry.status}`}>{STATUS_LABEL[entry.status] ?? entry.status}</Badge>
      </div>
      {entry.evidence && (
        // The actual retrieved headline that drove this status — auditable
        // rather than trust-me (see backend/app/subscription_tracker.py):
        // real Google News RSS results, classified by a rule-based regex,
        // never fabricated or LLM-guessed.
        <p style={{ fontSize: 11, color: "var(--text-tertiary)", margin: 0, paddingLeft: 22, fontStyle: "italic" }}>
          Source: {entry.evidence}
        </p>
      )}
    </div>
  );
}

export default function SubscriptionWindowsPage() {
  const { data, isLoading, isError } = useSubscriptionWindows();

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 860, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontWeight: 800, fontSize: 18, fontFamily: "var(--font-display)" }}>Subscription Window</span>
        <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{(data ?? []).length} tracked</span>
      </div>

      {isLoading && <p style={{ color: "var(--text-tertiary)" }}>Loading subscription windows…</p>}
      {isError && <p style={{ color: "var(--text-negative)" }}>Couldn't load subscription windows.</p>}
      {data && data.length === 0 && <p style={{ color: "var(--text-tertiary)", fontSize: 14 }}>Nothing tracked yet.</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: 12 }}>
        {(data ?? []).map((entry) => (
          <Row key={entry.instrument_id} entry={entry} />
        ))}
      </div>
    </div>
  );
}
