// Ported from kit/components/core/Button.jsx — "buy"/"sell" variants
// deliberately dropped (see the phase's flagged conflict with
// docs/SOURCE_OF_TRUTH.md's ban on order-execution/buy-sell language).
const SIZES = {
  sm: { padding: "10px 20px", font: "var(--text-body-sm)" },
  md: { padding: "16px 24px", font: "var(--text-body-lg)" },
  lg: { padding: "18px 24px", font: "var(--text-body-lg)" },
} as const;

const VARIANTS: Record<string, { background: string; color: string; boxShadow?: string }> = {
  primary: { background: "var(--accent-primary)", color: "var(--text-inverse)" },
  secondary: { background: "var(--surface-chip)", color: "var(--text-primary)" },
  outline: { background: "transparent", color: "var(--text-primary)", boxShadow: "inset 0 0 0 1px var(--border-default)" },
  ghost: { background: "transparent", color: "var(--text-secondary)" },
};

export function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  disabled = false,
  children,
  onClick,
  type = "button",
}: {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  fullWidth?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
}) {
  const v = VARIANTS[variant] ?? VARIANTS.primary;
  const s = SIZES[size] ?? SIZES.md;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "var(--font-body)",
        fontWeight: 600,
        fontSize: s.font,
        lineHeight: "100%",
        border: "none",
        borderRadius: "var(--radius-lg)",
        cursor: disabled ? "default" : "pointer",
        padding: s.padding,
        width: fullWidth ? "100%" : "auto",
        opacity: disabled ? 0.45 : 1,
        ...v,
      }}
    >
      {children}
    </button>
  );
}
