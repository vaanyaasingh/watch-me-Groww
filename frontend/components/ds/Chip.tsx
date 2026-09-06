// Ported from kit/components/core/Chip.jsx, restyled with the glass
// treatment (see ./glass.ts) instead of the flat card-border shadow.
import { glassCard } from "./glass";

export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 600,
        fontSize: "var(--text-label)",
        padding: "6px 15px",
        borderRadius: "var(--radius-md)",
        color: "var(--text-primary)",
        whiteSpace: "nowrap",
        display: "inline-flex",
        ...glassCard,
      }}
    >
      {children}
    </span>
  );
}
