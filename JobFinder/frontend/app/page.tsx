"use client";

import { useIsAuthenticated } from "@azure/msal-react";
import Link from "next/link";

import { LoginButton } from "@/components/LoginButton";

export default function Home() {
  const isAuthenticated = useIsAuthenticated();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <h1 className="text-3xl font-bold">job-finder</h1>
      <p className="text-gray-600">Walking skeleton — authentification Entra External ID</p>
      <LoginButton />
      {isAuthenticated && (
        <Link href="/profile" className="text-sm text-blue-600 hover:underline">
          Mon profil →
        </Link>
      )}
    </main>
  );
}
