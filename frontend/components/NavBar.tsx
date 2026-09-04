"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Feed" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/subscriptions", label: "Subscriptions" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header style={{ display: "flex", alignItems: "center", gap: 16, padding: "14px 24px", background: "var(--surface-card)", borderBottom: "1px solid var(--border-default)", flexWrap: "wrap" }}>
      <span style={{ fontWeight: 600, fontSize: 14, fontFamily: "var(--font-display)", whiteSpace: "nowrap" }}>Smart Market Watchlist</span>
      <nav style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              style={{
                padding: "8px 14px",
                borderRadius: 20,
                fontSize: 13,
                fontFamily: "var(--font-body)",
                fontWeight: active ? 600 : 400,
                background: active ? "var(--ink-0)" : "var(--surface-chip)",
                color: active ? "#fff" : "var(--text-primary)",
                textDecoration: "none",
              }}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
