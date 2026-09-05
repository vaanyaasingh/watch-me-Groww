// Visual direction only — not a port of Apple's native Liquid Glass APIs
// (glassEffect(), GlassEffectContainer, etc. are SwiftUI/UIKit-only and
// don't apply to a web app). This is the CSS equivalent of that aesthetic:
// frosted translucency, blur, depth — layered on top of this project's
// existing Groww design tokens (app/design-tokens.css) rather than
// replacing them, so surfaces still read as this app, not a generic kit.
import type { CSSProperties } from "react";

export const glassCard: CSSProperties = {
  background: "rgba(255, 255, 255, 0.6)",
  backdropFilter: "blur(20px) saturate(160%)",
  WebkitBackdropFilter: "blur(20px) saturate(160%)",
  border: "1px solid rgba(255, 255, 255, 0.7)",
  boxShadow: "0 8px 32px rgba(31, 41, 55, 0.08)",
};

export const glassCardHover: CSSProperties = {
  ...glassCard,
  background: "rgba(255, 255, 255, 0.75)",
};

export const glassNav: CSSProperties = {
  background: "rgba(255, 255, 255, 0.55)",
  backdropFilter: "blur(24px) saturate(160%)",
  WebkitBackdropFilter: "blur(24px) saturate(160%)",
  borderBottom: "1px solid rgba(255, 255, 255, 0.6)",
};

export const glassPillActive: CSSProperties = {
  background: "var(--ink-0)",
  color: "#fff",
  boxShadow: "0 4px 14px rgba(0, 0, 0, 0.18)",
};

export const glassPillInactive: CSSProperties = {
  background: "rgba(255, 255, 255, 0.5)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid rgba(255, 255, 255, 0.6)",
  color: "var(--text-primary)",
};
