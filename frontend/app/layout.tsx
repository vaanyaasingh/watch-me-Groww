import "./globals.css";
import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Smart Market Watchlist",
  description: "Since-you-last-checked digests and significance-ranked alerts for your watchlist.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ minHeight: "100vh" }}>
        <Providers>
          <NavBar />
          <main className="px-3 py-6 sm:px-6" style={{ maxWidth: 960, margin: "0 auto" }}>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
