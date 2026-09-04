// Ported from kit/components/forms/Switch.jsx.
export function Switch({ checked = false, onChange }: { checked?: boolean; onChange?: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange?.(!checked)}
      style={{
        width: 44,
        height: 26,
        borderRadius: "var(--radius-pill)",
        border: "none",
        cursor: "pointer",
        background: checked ? "var(--accent-primary)" : "var(--gray-300)",
        padding: 3,
        flexShrink: 0,
        display: "flex",
        justifyContent: checked ? "flex-end" : "flex-start",
        boxSizing: "border-box",
        transition: "background .15s ease",
      }}
    >
      <span style={{ width: 20, height: 20, borderRadius: "50%", background: "var(--white)", display: "block", flexShrink: 0 }} />
    </button>
  );
}
