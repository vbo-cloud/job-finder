"use client";

import { useEffect, useRef } from "react";
import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";

import { useConsent } from "@/lib/consent/ConsentContext";

/**
 * Wraps the application in a PostHog client that only initializes once the user
 * has explicitly accepted analytics cookies (ePrivacy/CNIL: no cookie, no
 * capture before opt-in). The many `posthog.capture(...)` calls across the app
 * are safe no-ops until `init()` runs here, so they need no consent guard of
 * their own.
 *
 * Analytics is treated as non-critical: if `NEXT_PUBLIC_POSTHOG_KEY`/`_HOST`
 * are absent, it logs a warning and skips `init()` instead of throwing —
 * children still render normally either way.
 */
export function PostHogProvider({ children }: { children: React.ReactNode }) {
  const { consent } = useConsent();
  const initialized = useRef(false);

  useEffect(() => {
    // Branch explicitly on all three states so a consent *transition* on a
    // mounted provider (accept -> decline -> re-accept via "Gérer les cookies")
    // is handled — not just the first-mount case.
    if (consent === "accepted") {
      if (initialized.current) {
        // Already loaded once, so init() would be a no-op — but if the user had
        // previously withdrawn, opt_out_capturing() is still in effect and only
        // opt_in_capturing() re-enables capture. Re-accepting must resume it.
        posthog.opt_in_capturing();
        return;
      }
      // Read statically (required for Next.js to inline NEXT_PUBLIC_* at build
      // time) but only inside the effect: the root layout has no
      // global-error.tsx, so a module-level throw would crash every route.
      const posthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;
      const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST;
      if (!posthogKey || !posthogHost) {
        console.warn(
          "[jf] PostHog disabled: NEXT_PUBLIC_POSTHOG_KEY/NEXT_PUBLIC_POSTHOG_HOST not set.",
        );
        return;
      }
      posthog.init(posthogKey, {
        api_host: posthogHost,
        // "2026-05-30" sets capture_pageview: "history_change", which already
        // autocaptures $pageview on App Router client-side navigation — no
        // manual usePathname()-driven capture needed on top of this.
        defaults: "2026-05-30",
      });
      initialized.current = true;
      return;
    }

    // Withdrawal: the user changed their mind (accepted -> declined). Stop
    // capturing and drop the identified profile. Nothing to do if PostHog was
    // never loaded (a fresh decline sets no cookie and writes no opt-out flag).
    if (consent === "declined" && initialized.current) {
      posthog.opt_out_capturing();
      posthog.reset();
    }

    // consent === null (re-deciding window after "Gérer les cookies"): leave
    // PostHog in its current state until the user picks again — deliberately no
    // change here.
  }, [consent]);

  return <PHProvider client={posthog}>{children}</PHProvider>;
}
