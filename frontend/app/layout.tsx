import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ShipRocket AI — D2C Intelligence Platform",
  description:
    "AI employee platform for D2C brands — citation-grounded chat, autonomous agents, and multi-platform data connectors.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface text-gray-100 min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-64 bg-grid min-h-screen">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
