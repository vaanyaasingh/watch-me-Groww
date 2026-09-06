// Solid-fill pills, not tinted outlines — the mockup's attention/status
// badges are the attention color itself as a background with bold white
// text, not a pale tint (that treatment moved to the narrative/status
// boxes instead, see design-tokens.css's green-50/red-50/amber-50). Amber
// fills keep dark ink text rather than white — white-on-amber reads too
// low-contrast, exactly the same reasoning as --text-inverse in
// design-tokens.css.
const KINDS: Record<string, { background: string; color: string }> = {
  "attention-high": { background: "var(--attention-high)", color: "#fff" },
  "attention-medium": { background: "var(--attention-medium)", color: "var(--ink)" },
  "attention-low": { background: "var(--attention-low)", color: "#fff" },
  "status-open": { background: "var(--status-open)", color: "#fff" },
  "status-closing": { background: "var(--status-closing)", color: "var(--ink)" },
  "status-closed": { background: "var(--status-closed)", color: "#fff" },
  neutral: { background: "var(--surface-chip)", color: "var(--text-secondary)" },
};

export function Badge({ kind = "neutral", children }: { kind?: string; children: React.ReactNode }) {
  const k = KINDS[kind] ?? KINDS.neutral;
  return (
    <span
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 800,
        fontSize: "var(--text-caption)",
        padding: "4px 10px",
        borderRadius: "var(--radius-pill)",
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        whiteSpace: "nowrap",
        letterSpacing: "0.3px",
        ...k,
      }}
    >
      {children}
    </span>
  );
}
