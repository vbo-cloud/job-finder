"use client";

import { LoginButton } from "@/components/LoginButton";

/**
 * Home page — auth skeleton only.
 *
 * No business UI here (no CV upload, no library): this PR scaffolds the
 * project and the MSAL authentication shell. The page renders a single
 * sign-in / sign-out control that reflects the current auth state.
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <h1 className="text-3xl font-bold">job-finder</h1>
      <p className="text-gray-600">Walking skeleton — authentification Entra External ID</p>
      <LoginButton />
    </main>
  );
}
