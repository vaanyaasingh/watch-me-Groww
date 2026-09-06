"use client";

import { FirebaseError } from "firebase/app";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ds/Button";
import { glassCard } from "@/components/ds/glass";
import { signIn, signUp } from "@/lib/auth";

// Firebase's own error codes, translated to something a person filling out
// a form actually understands — its default messages ("Firebase: Error
// (auth/wrong-password).") are implementation detail, not UI copy.
function friendlyAuthError(error: unknown): string {
  if (error instanceof FirebaseError) {
    switch (error.code) {
      case "auth/email-already-in-use":
        return "That email already has an account — try signing in instead.";
      case "auth/invalid-credential":
      case "auth/wrong-password":
      case "auth/user-not-found":
        return "Incorrect email or password.";
      case "auth/weak-password":
        return "Password must be at least 6 characters.";
      case "auth/invalid-email":
        return "That doesn't look like a valid email address.";
      case "auth/too-many-requests":
        return "Too many attempts — wait a moment and try again.";
      default:
        return `Something went wrong (${error.code}).`;
    }
  }
  return "Something went wrong. Please try again.";
}

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "signup") {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      router.push("/");
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setSubmitting(false);
    }
  }

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
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 800, letterSpacing: "-0.4px", marginBottom: 8 }}>
          Smart Market Watchlist
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 32 }}>
          Know what actually changed since you last checked — not another price ticker.
        </p>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 12, padding: 24, borderRadius: "var(--radius-lg)", ...glassCard, textAlign: "left" }}
        >
          <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
            {(["signin", "signup"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                style={{
                  flex: 1,
                  padding: "8px 0",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: 600,
                  background: mode === m ? "var(--accent-primary)" : "transparent",
                  color: mode === m ? "var(--text-inverse)" : "var(--text-secondary)",
                }}
              >
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              autoComplete="email"
              required
              style={{ width: "100%", marginTop: 6, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-page)", color: "var(--text-primary)", fontSize: 14 }}
            />
          </label>
          <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Password
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={6}
              required
              style={{ width: "100%", marginTop: 6, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)", background: "var(--surface-page)", color: "var(--text-primary)", fontSize: 14 }}
            />
          </label>

          {error && (
            <p style={{ fontSize: 13, color: "var(--text-negative)", margin: 0 }} role="alert">
              {error}
            </p>
          )}

          <Button variant="primary" size="lg" fullWidth type="submit" disabled={submitting}>
            {submitting ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}
          </Button>
          <p style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 4 }}>
            Real accounts via Firebase Authentication — your password is never seen by this app's own backend, only
            Firebase's servers.
          </p>
        </form>
      </div>
    </div>
  );
}
