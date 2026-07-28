"use client";

import { useConsent } from "@/lib/consent/ConsentContext";
import { cn } from "@/lib/utils";

/**
 * Re-opens the cookie consent bar so the user can change (withdraw) their
 * choice — RGPD requires withdrawal to be as easy as giving consent. Rendered
 * next to the legal links so it's reachable from every page. Client island
 * inside the otherwise-static LegalLinks.
 */
export default function ManageCookiesButton({ className }: { className?: string }) {
  const { reopen } = useConsent();

  return (
    <button
      type="button"
      onClick={reopen}
      // Carry an intrinsic focus-visible style so the button stays keyboard-
      // accessible even if a caller passes no (or a focus-less) className.
      className={cn(
        "rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
        className,
      )}
    >
      Gérer les cookies
    </button>
  );
}
