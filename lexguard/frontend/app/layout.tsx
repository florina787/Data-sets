import type { Metadata } from "next";
import "./globals.css";
import { AppStateProvider } from "@/hooks/useAppState";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "LexGuard Copilot",
  description: "Govern AI. Protect matters. Prove value. A governed legal matter copilot (synthetic demo).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppStateProvider>
          <AppShell>{children}</AppShell>
        </AppStateProvider>
      </body>
    </html>
  );
}
