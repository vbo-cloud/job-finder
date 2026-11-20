"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

/** A settled cookie-consent choice. `null` means the user hasn't chosen yet. */
export type ConsentValue = "accepted" | "declined";
type StoredConsent = ConsentValue | null;

const STORAGE_KEY = "jf-cookie-consent";

interface ConsentContextValue {
  consent: StoredConsent;
  /** True once the initial localStorage read has run. The banner must wait for
   * this before rendering, otherwise it flashes on every load before the stored
   * choice is known (and would re-ask a user who already decided). */
  hydrated: boolean;
  accept: () => void;
  decline: () => void;
  /** Re-open the choice (RGPD withdrawal, must be as easy as consenting):
   * clears the stored value so the banner shows again. */
  reopen: () => void;
}

const ConsentContext = createContext<ConsentContextValue | null>(null);

/**
 * Holds the analytics cookie-consent choice, persisted in `localStorage`.
 *
 * Storing the choice itself needs no consent — it is strictly necessary to
 * honour the user's decision (ePrivacy exemption). Auth (MSAL) cookies are
 * essential and never gated here; only analytics (PostHog) is, via
 * `PostHogProvider` reading this context.
 */
export function ConsentProvider({ children }: { children: React.ReactNode }) {
  const [consent, setConsentState] = useState<StoredConsent>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "accepted" || stored === "declined") {
        setConsentState(stored);
      }
    } catch {
      // localStorage unavailable (private mode, storage disabled) — treat as
      // "no choice yet"; nothing is captured until an explicit opt-in anyway.
    }
    setHydrated(true);
  }, []);

  const persist = useCallback((value: StoredConsent) => {
    try {
      if (value === null) localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Best-effort persistence: the in-memory state still drives the UI and
      // PostHog gating for this session even if storage writes fail.
    }
    setConsentState(value);
  }, []);

  const accept = useCallback(() => persist("accepted"), [persist]);
  const decline = useCallback(() => persist("declined"), [persist]);
  const reopen = useCallback(() => persist(null), [persist]);

  return (
    <ConsentContext.Provider value={{ consent, hydrated, accept, decline, reopen }}>
      {children}
    </ConsentContext.Provider>
  );
}

export function useConsent(): ConsentContextValue {
  const ctx = useContext(ConsentContext);
  if (!ctx) {
    throw new Error("useConsent must be used within a ConsentProvider");
  }
  return ctx;
}
