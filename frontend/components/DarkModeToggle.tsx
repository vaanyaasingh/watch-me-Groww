"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "smw-theme";

export function DarkModeToggle() {
  // Starts null (unknown) until mounted, so this never renders a guess
  // that mismatches whatever the blocking inline script in layout.tsx
  // already applied to <html> before hydration.
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);

  useEffect(() => {
    setTheme((document.documentElement.dataset.theme as "dark") || "light");
  }, []);

  if (theme === null) return null;

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage can throw in private-browsing contexts — the toggle
      // still works for this page load, it just won't persist.
    }
    setTheme(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        marginLeft: "auto",
        border: "1px solid var(--glass-border)",
        background: "var(--glass-bg)",
        borderRadius: 20,
        padding: "8px 12px",
        fontSize: 13,
        cursor: "pointer",
        color: "var(--text-primary)",
      }}
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
