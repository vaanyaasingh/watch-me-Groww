// Ported from kit/components/core/Chip.jsx — restyled to the mockup's
// sector-tag look (a muted tan pill, e.g. "Consumer Services" on the
// digest header) rather than a bordered card.
export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 700,
        fontSize: "var(--text-label)",
        padding: "5px 12px",
        borderRadius: "var(--radius-pill)",
        background: "var(--surface-chip)",
        color: "var(--text-secondary)",
        whiteSpace: "nowrap",
        display: "inline-flex",
      }}
    >
      {children}
    </span>
  );
}
