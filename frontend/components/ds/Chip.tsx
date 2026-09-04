// Ported from kit/components/core/Chip.jsx.
export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 600,
        fontSize: "var(--text-label)",
        padding: "6px 15px",
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-card-border)",
        color: "var(--ink-5)",
        whiteSpace: "nowrap",
        display: "inline-flex",
      }}
    >
      {children}
    </span>
  );
}
