import type { Metadata } from "next";
import { Inter } from "next/font/google";

import AuthButton from "@/app/_components/AuthButton";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/utils";

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
        <AuthProvider>
          <div className="fixed right-3 top-2 z-50">
            <AuthButton />
          </div>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
