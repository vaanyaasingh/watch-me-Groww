"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { glassNav, glassPillActive, glassPillInactive } from "./ds/glass";

const LINKS = [
  { href: "/", label: "Feed" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/subscriptions", label: "Subscriptions" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "14px 24px",
        flexWrap: "wrap",
        ...glassNav,
      }}
    >
      <span style={{ fontWeight: 600, fontSize: 14, fontFamily: "var(--font-display)", whiteSpace: "nowrap" }}>
        Smart Market Watchlist
      </span>
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
                textDecoration: "none",
                transition: "background .15s ease",
                ...(active ? glassPillActive : glassPillInactive),
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
