"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DarkModeToggle } from "./DarkModeToggle";
import { glassNav, glassPillActive, glassPillInactive } from "./ds/glass";

const LINKS = [
  { href: "/", label: "Feed" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/subscriptions", label: "Subscriptions" },
  { href: "/profile", label: "Profile" },
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
        flexDirection: "column",
        gap: 10,
        padding: "12px 16px",
        ...glassNav,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span style={{ fontWeight: 800, fontSize: 15, fontFamily: "var(--font-display)", color: "#fff", letterSpacing: "-0.2px", whiteSpace: "nowrap" }}>
          Smart Market Watchlist
        </span>
        <DarkModeToggle />
      </div>
      {/* A fixed two-row bar (brand+toggle, then this scrollable strip)
          rather than letting the pills wrap — wrapping 5 pills at a phone
          width used to push the toggle onto its own third row and eat a
          third of the screen before any content appeared. Scrolling
          horizontally keeps the bar's height constant regardless of
          viewport width or how many links there are. */}
      <nav
        style={{
          display: "flex",
          gap: 6,
          overflowX: "auto",
          WebkitOverflowScrolling: "touch",
          scrollbarWidth: "none",
        }}
      >
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
                fontWeight: active ? 800 : 500,
                textDecoration: "none",
                whiteSpace: "nowrap",
                flexShrink: 0,
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
