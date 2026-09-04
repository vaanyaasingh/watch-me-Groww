// Ported from kit/components/core/Badge.jsx.
const KINDS: Record<string, { background: string; color: string }> = {
  "attention-high": { background: "var(--red-50)", color: "var(--attention-high)" },
  "attention-medium": { background: "#fdf3e4", color: "var(--attention-medium)" },
  "attention-low": { background: "var(--green-50)", color: "var(--attention-low)" },
  "status-open": { background: "var(--green-50)", color: "var(--status-open)" },
  "status-closing": { background: "#fdf3e4", color: "var(--status-closing)" },
  "status-closed": { background: "var(--gray-100)", color: "var(--status-closed)" },
  neutral: { background: "var(--surface-chip)", color: "var(--text-secondary)" },
};

export function Badge({ kind = "neutral", children }: { kind?: string; children: React.ReactNode }) {
  const k = KINDS[kind] ?? KINDS.neutral;
  return (
    <span
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 600,
        fontSize: "var(--text-caption)",
        padding: "4px 10px",
        borderRadius: "var(--radius-pill)",
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        whiteSpace: "nowrap",
        letterSpacing: "0.2px",
        ...k,
      }}
    >
      {children}
    </span>
  );
}
