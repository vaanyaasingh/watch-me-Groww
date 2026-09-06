"use client";

import { usePathname } from "next/navigation";
import { AuthGate } from "./AuthGate";
import { NavBar } from "./NavBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  return (
    <AuthGate>
      {!isLoginPage && <NavBar />}
      <main className={isLoginPage ? "" : "px-3 py-6 sm:px-6"} style={isLoginPage ? undefined : { maxWidth: 960, margin: "0 auto" }}>
        {children}
      </main>
      {/* Persistent on every screen (including /login) per
          docs/SOURCE_OF_TRUTH.md's non-goals — this app surfaces
          significance/narrative content that could otherwise read as a
          recommendation if the boundary weren't stated explicitly. */}
      <footer style={{ textAlign: "center", padding: "20px 16px 28px", fontSize: 11, color: "var(--text-tertiary)" }}>
        Informational only — not investment advice. Nothing here is a recommendation to buy, sell, or hold any
        security.
      </footer>
    </AuthGate>
  );
}
