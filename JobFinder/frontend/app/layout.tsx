import type { Metadata } from "next";
import { Inter } from "next/font/google";

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
      <body className={cn(inter.className, "min-h-screen bg-gray-50 text-gray-900 antialiased")}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
