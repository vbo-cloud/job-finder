import type { Metadata } from "next";
import { Inter } from "next/font/google";

import AuthButton from "@/app/_components/AuthButton";
import CreditsBadge from "@/app/_components/CreditsBadge";
import MobileNavMenu from "@/app/_components/MobileNavMenu";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/utils";

import { PostHogProvider } from "./Providers";

import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "job-finder",
  description: "job-finder — AI-assisted job search",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className={cn(inter.className, "min-h-screen bg-page text-strong antialiased")}>
        <PostHogProvider>
          <AuthProvider>
            {/* Below md this is a full-width pinned opaque bar (burger menu on
                the left, credits + account on the right) — page content passes
                behind it, never over it. From md up it collapses back to the
                original floating pills in the top-right corner: same elements,
                repositioned purely in CSS so CreditsBadge/AuthButton mount once
                (a second instance would duplicate the GET /profile fetch). */}
            <header className="fixed inset-x-0 top-0 z-50 flex h-14 items-center justify-between border-b border-subtle bg-surface px-2 md:pointer-events-none md:inset-x-auto md:right-3 md:top-2 md:h-auto md:border-0 md:bg-transparent md:px-0">
              <div className="md:hidden">
                <MobileNavMenu />
              </div>
              <div className="pointer-events-auto flex items-center gap-2">
                <CreditsBadge />
                <AuthButton />
              </div>
            </header>
            {children}
          </AuthProvider>
        </PostHogProvider>
      </body>
    </html>
  );
}
