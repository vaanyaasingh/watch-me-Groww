// Solid "paper" cards, not frosted glass — the "Pulsewatch" visual
// direction (Claude Design project 3d1e8be7-495a-41be-a7dc-119b9ad32c4e)
// uses opaque white cards with a soft drop shadow on a flat cream page,
// replacing the earlier translucent/blurred treatment. Kept under the
// same export names as that earlier pass (glassCard, glassNav, ...) so
// every component that already imports them repaints from the new
// design-tokens.css values alone — only this file's actual CSS changed,
// no import needs to move.
import type { CSSProperties } from "react";

export const glassCard: CSSProperties = {
  background: "var(--glass-bg)",
  border: "1px solid var(--glass-border)",
  boxShadow: "var(--glass-shadow)",
};

export const glassCardHover: CSSProperties = {
  ...glassCard,
  background: "var(--glass-bg-strong)",
};

export const glassNav: CSSProperties = {
  background: "var(--nav-bg)",
};

// The active/inactive nav pills share the fixed dark nav bar's own
// palette (--nav-*), not the page's light/dark theme tokens — the mockup
// treats the top bar as a constant brand surface, not something that
// flips with the reader's theme choice.
export const glassPillActive: CSSProperties = {
  background: "var(--accent-primary)",
  color: "var(--text-inverse)",
};

export const glassPillInactive: CSSProperties = {
  background: "var(--nav-pill-inactive-bg)",
  color: "var(--nav-pill-inactive-text)",
};
