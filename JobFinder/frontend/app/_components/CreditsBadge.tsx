"use client";

import { useEffect, useState } from "react";
import { useIsAuthenticated } from "@azure/msal-react";
import { Coins } from "lucide-react";
import Link from "next/link";
import posthog from "posthog-js";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { onCreditsConsumed, onCreditsReleased, onCreditsReserved } from "@/lib/creditsBus";

/**
 * Pinned pill next to AuthButton showing the user's remaining analysis
 * credits (see ADR-018). Links to /profile — no purchase flow yet, that
 * page is where the balance is explained.
 */
export default function CreditsBadge() {
  const isAuthenticated = useIsAuthenticated();
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      setCredits(null);
      return;
    }

    const fetchCredits = () => {
      apiClient
        .get<ProfileData>("/profile")
        .then((res) => {
          setCredits(res.data.analysis_credits_remaining);
          posthog.setPersonProperties({
            analysis_credits_remaining: res.data.analysis_credits_remaining,
          });
        })
        .catch((err: unknown) => {
          const httpStatus = (err as { response?: { status?: number } })?.response?.status;
          if (httpStatus === 404) return; // no profile yet — nothing to show
          console.error("[jf] credits fetch failed:", err);
        });
    };

    fetchCredits();
    // Refetch after a manual match analysis consumes a credit elsewhere in
    // the tree — the balance would otherwise go stale until the next mount.
    const unsubConsumed = onCreditsConsumed(fetchCredits);
    // Optimistic -1/+1 around the request itself, so the badge reacts the
    // instant the user clicks instead of waiting on the round-trip, and rolls
    // back cleanly if the request never actually consumed a credit.
    const unsubReserved = onCreditsReserved(() => {
      setCredits((c) => (c === null ? c : Math.max(0, c - 1)));
    });
    const unsubReleased = onCreditsReleased(() => {
      setCredits((c) => (c === null ? c : c + 1));
    });
    return () => {
      unsubConsumed();
      unsubReserved();
      unsubReleased();
    };
  }, [isAuthenticated]);

  if (!isAuthenticated || credits === null) return null;

  return (
    <Link
      href="/profile"
      title="Crédits d'analyse restants"
      className="flex h-8 items-center gap-1.5 rounded-full border border-soft bg-card px-3 text-xs text-primary transition-colors hover:border-default hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
    >
      <Coins className="h-3.5 w-3.5" />
      {credits}
    </Link>
  );
}
