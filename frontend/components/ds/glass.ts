// Visual direction only — not a port of Apple's native Liquid Glass APIs
// (glassEffect(), GlassEffectContainer, etc. are SwiftUI/UIKit-only and
// don't apply to a web app). This is the CSS equivalent of that aesthetic:
// frosted translucency, blur, depth — layered on top of this project's
// existing Groww design tokens (app/design-tokens.css) rather than
// replacing them, so surfaces still read as this app, not a generic kit.
//
// Colors are CSS variables, not hardcoded rgba(), specifically so dark
// mode (design-tokens.css's :root[data-theme="dark"] block) flips every
// glass surface in the app at once.
import type { CSSProperties } from "react";

export const glassCard: CSSProperties = {
  background: "var(--glass-bg)",
  backdropFilter: "blur(20px) saturate(160%)",
  WebkitBackdropFilter: "blur(20px) saturate(160%)",
  border: "1px solid var(--glass-border)",
  boxShadow: "var(--glass-shadow)",
};

export const glassCardHover: CSSProperties = {
  ...glassCard,
  background: "var(--glass-bg-strong)",
};

export const glassNav: CSSProperties = {
  background: "var(--glass-bg)",
  backdropFilter: "blur(24px) saturate(160%)",
  WebkitBackdropFilter: "blur(24px) saturate(160%)",
  borderBottom: "1px solid var(--glass-border)",
};

export const glassPillActive: CSSProperties = {
  background: "var(--ink-0)",
  color: "var(--text-inverse)",
  boxShadow: "0 4px 14px rgba(0, 0, 0, 0.18)",
};

export const glassPillInactive: CSSProperties = {
  background: "var(--glass-bg)",
  backdropFilter: "blur(12px)",
  WebkitBackdropFilter: "blur(12px)",
  border: "1px solid var(--glass-border)",
  color: "var(--text-primary)",
};
