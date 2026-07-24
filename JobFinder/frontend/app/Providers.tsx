"use client";

import { useEffect } from "react";
import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";

/**
 * Wraps the application in an initialized PostHog client.
 *
 * Analytics is treated as non-critical: if `NEXT_PUBLIC_POSTHOG_KEY`/`_HOST`
 * are absent, it logs a warning and skips `init()` instead of throwing —
 * children still render normally either way.
 */
export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Unlike lib/auth/msalConfig.ts's requireEnv() (fail-fast is right there:
    // without MSAL vars the app has no auth and shouldn't pretend otherwise),
    // this module is imported by the root layout, which has no
    // global-error.tsx to catch a module-level throw — that would crash every
    // route. Analytics is non-critical: read statically (required for Next.js
    // to inline NEXT_PUBLIC_* at build time) but only inside the effect, and
    // degrade gracefully — same failure mode already documented for "GitHub
    // repo vars not yet created" (docs/JOURNAL.md, PR #221).
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
  }, []);

  return <PHProvider client={posthog}>{children}</PHProvider>;
}
