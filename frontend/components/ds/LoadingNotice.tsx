"use client";

import { useEffect, useState } from "react";

// The free-tier backend (Render) and database (Neon) both suspend after
// ~15 minutes idle — the first request after that can take 30-50s while
// they wake up, occasionally needing one retry. Most loads are instant;
// this only shows the explanation once a load has genuinely been slow for
// a few seconds, so it never appears on the common fast path.
const SLOW_LOAD_THRESHOLD_MS = 4000;

export function LoadingNotice({ label }: { label: string }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_LOAD_THRESHOLD_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <p style={{ color: "var(--text-tertiary)", margin: 0 }}>{label}</p>
      {slow && (
        <p style={{ color: "var(--text-tertiary)", fontSize: 12, margin: 0, fontStyle: "italic" }}>
          Taking longer than usual? The server sleeps after a few minutes idle (free hosting) — it can take up to a
          minute to wake up, and very occasionally needs a page refresh once it's up. Thanks for your patience.
        </p>
      )}
    </div>
  );
}
