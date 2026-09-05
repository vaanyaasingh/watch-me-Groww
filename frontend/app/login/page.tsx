"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ds/Button";
import { glassCard } from "@/components/ds/glass";
import { logIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@example.com");

  return (
    <div
      style={{
        minHeight: "calc(100vh - 64px)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 420, width: "100%" }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 600, marginBottom: 8 }}>
          Smart Market Watchlist
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 32 }}>
          Know what actually changed since you last checked — not another price ticker.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            // Mock sign-in only — see lib/auth.ts. No password is checked
            // against anything real; this just unlocks the demo.
            logIn();
            router.push("/");
          }}
          style={{ display: "flex", flexDirection: "column", gap: 12, padding: 24, borderRadius: "var(--radius-lg)", ...glassCard, textAlign: "left" }}
        >
          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
              style={{ width: "100%", marginTop: 6, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-page)", color: "var(--text-primary)", fontSize: 14 }}
            />
          </label>
          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Password
            <input
              type="password"
              defaultValue="demo"
              required
              style={{ width: "100%", marginTop: 6, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-page)", color: "var(--text-primary)", fontSize: 14 }}
            />
          </label>
          <Button variant="primary" size="lg" fullWidth type="submit">
            Sign in
          </Button>
          <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
            Demo mode — any email/password signs you in as the single demo user this project runs on. No real auth is
            wired up yet (see docs/plan.md §4).
          </p>
        </form>
      </div>
    </div>
  );
}
