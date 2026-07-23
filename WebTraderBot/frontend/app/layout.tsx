import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WebTraderBot - Multi-Crypto Dashboard",
  description: "Next.js App Router Trading Dashboard for Bitkub",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="th" className="h-full bg-[#0a0d14] text-white">
      <body className="min-h-full flex flex-col antialiased">{children}</body>
    </html>
  );
}
