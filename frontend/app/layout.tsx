import "./globals.css";
import type { Metadata } from "next";

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
      <body>{children}</body>
    </html>
  );
}
