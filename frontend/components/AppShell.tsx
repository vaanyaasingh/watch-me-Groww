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
    </AuthGate>
  );
}
