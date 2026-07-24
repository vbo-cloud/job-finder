"use client";

import { useEffect } from "react";
import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";

// Next.js only inlines NEXT_PUBLIC_* into the client bundle when referenced
// statically (process.env.NEXT_PUBLIC_FOO), so the value is read this way and
// validated, same pattern as lib/auth/msalConfig.ts.
function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const posthogKey = requireEnv("NEXT_PUBLIC_POSTHOG_KEY", process.env.NEXT_PUBLIC_POSTHOG_KEY);
const posthogHost = requireEnv("NEXT_PUBLIC_POSTHOG_HOST", process.env.NEXT_PUBLIC_POSTHOG_HOST);

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
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
