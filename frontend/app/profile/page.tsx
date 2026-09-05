"use client";

import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ds/Avatar";
import { Button } from "@/components/ds/Button";
import { glassCard } from "@/components/ds/glass";
import { logOut } from "@/lib/auth";
import { useMe } from "@/lib/hooks";

export default function ProfilePage() {
  const router = useRouter();
  const { data, isLoading } = useMe();

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 420, margin: "0 auto" }}>
      <div style={{ padding: 24, borderRadius: "var(--radius-lg)", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, ...glassCard }}>
        <Avatar label={data?.email ?? "?"} size="xl" />
        {isLoading && <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>Loading…</p>}
        {data && (
          <>
            <span style={{ fontSize: 16, fontWeight: 500 }}>{data.email}</span>
            <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{data.watchlist_count} instruments tracked</span>
          </>
        )}
        <p style={{ fontSize: 11, color: "var(--text-tertiary)", textAlign: "center", marginTop: 4 }}>
          Single demo user — no real accounts exist yet (Firebase Auth is a later phase, see docs/plan.md §4).
        </p>
        <Button
          variant="outline"
          size="md"
          onClick={() => {
            logOut();
            router.push("/login");
          }}
        >
          Log out
        </Button>
      </div>
    </div>
  );
}
