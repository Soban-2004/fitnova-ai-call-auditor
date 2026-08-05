import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { LiveUpdates } from "@/components/layout/LiveUpdates";

export const metadata: Metadata = {
  title: "FitNova Call Intelligence",
  description: "Sales-call quality dashboard — director, team, and advisor views",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <LiveUpdates />
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="min-w-0 flex-1 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
