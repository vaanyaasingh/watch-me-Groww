"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { subscribeToAuthState } from "@/lib/auth";

/** Real Firebase auth gate — redirects to /login when nobody's signed in.
 * Subscribes rather than doing a one-off check, since Firebase restores a
 * signed-in session asynchronously on page load (see lib/auth.ts's
 * waitForAuthReady): reading the auth state once at mount could catch it
 * mid-restore and redirect someone who's actually logged in. Renders
 * nothing until the first auth-state callback fires, to avoid a flash of
 * gated content before a redirect (or of the login page for someone who
 * turns out to already be signed in). */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [status, setStatus] = useState<"checking" | "authed" | "anon">("checking");

  useEffect(() => {
    const unsubscribe = subscribeToAuthState((user) => {
      setStatus(user ? "authed" : "anon");
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (status === "anon" && pathname !== "/login") {
      router.replace("/login");
    }
    if (status === "authed" && pathname === "/login") {
      router.replace("/");
    }
  }, [status, pathname, router]);

  if (pathname === "/login") {
    return status === "authed" ? null : <>{children}</>;
  }
  if (status !== "authed") return null;
  return <>{children}</>;
}
