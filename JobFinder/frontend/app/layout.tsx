import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth/AuthProvider";

import "./globals.css";

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
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
