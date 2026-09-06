// Ported from the Claude Design export (kit/components/core/Avatar.jsx).
// Real instruments in this app (RELIANCE.NS, TCS.NS, ...) have no logo
// assets — unlike the design's demo data (Zomato, Swiggy, BSE, ...), which
// had real company logos. Falling back to the first letters of the ticker
// keeps every card from rendering the same flat gray square.
const SIZES = { sm: 24, md: 35, lg: 45, xl: 100 } as const;

export function Avatar({
  src,
  alt = "",
  size = "md",
  shape = "circle",
  label,
  background,
  color,
}: {
  src?: string;
  alt?: string;
  size?: keyof typeof SIZES;
  shape?: "circle" | "square";
  label?: string;
  // Attention-colored tiles (the feed's per-instrument avatar) need a
  // caller-chosen fill rather than the neutral default every other screen
  // uses (watchlist rows, digest header, subscription tracker) — optional
  // so those call sites don't change.
  background?: string;
  color?: string;
}) {
  const px = SIZES[size] ?? 35;
  const initials = (label ?? alt).replace(/\.(NS|BO)$/, "").slice(0, 2).toUpperCase();

  return (
    <div
      role="img"
      aria-label={alt}
      style={{
        width: px,
        height: px,
        borderRadius: shape === "circle" ? "var(--radius-circle)" : "var(--radius-sm)",
        overflow: "hidden",
        background: src ? `url(${src}) center/cover no-repeat` : background ?? "var(--surface-chip)",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-display)",
        fontWeight: 700,
        fontSize: Math.max(10, px * 0.32),
        color: color ?? "var(--ink-0)",
      }}
    >
      {!src && initials}
    </div>
  );
}
