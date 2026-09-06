import "./globals.css";
import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "watch-me-Groww",
  description: "Since-you-last-checked digests and significance-ranked alerts for your watchlist.",
};

// Applies a saved dark-mode choice to <html> before first paint, so there's
// no flash of the light theme on reload. Deliberately a plain blocking
// <script> in <head> (not next/script) — it must run before React
// hydrates; suppressHydrationWarning on <html> below silences the
// (expected, harmless) attribute mismatch React would otherwise warn about.
const themeInitScript = `
(function () {
  try {
    var theme = localStorage.getItem("smw-theme");
    if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body style={{ minHeight: "100vh" }}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
