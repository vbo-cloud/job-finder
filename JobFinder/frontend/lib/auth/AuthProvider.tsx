"use client";

import { EventType } from "@azure/msal-browser";
import type { AuthenticationResult } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import posthog from "posthog-js";
import { useEffect, useState } from "react";

import { msalInstance } from "./msalInstance";

/**
 * Wraps the application in an initialized `MsalProvider`.
 *
 * MSAL v3 requires `initialize()` to be awaited before any other API call, so
 * the children are gated until initialization completes. A login-success event
 * callback promotes the authenticated account to the active account.
 *
 * If initialization fails (e.g. a malformed authority), the error is surfaced
 * as a visible message rather than swallowed — never a silent blank screen.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isReady, setIsReady] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  useEffect(() => {
    let callbackId: string | null = null;

    msalInstance
      .initialize()
      .then(() => {
        const accounts = msalInstance.getAllAccounts();
        if (accounts.length > 0 && !msalInstance.getActiveAccount()) {
          msalInstance.setActiveAccount(accounts[0]);
        }

        callbackId = msalInstance.addEventCallback((event) => {
          if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const result = event.payload as AuthenticationResult;
            msalInstance.setActiveAccount(result.account);
            // homeAccountId, not username (= email) — avoids PII in the distinct_id.
            posthog.identify(result.account.homeAccountId);
            posthog.capture("user_logged_in");
          }
        });

        setIsReady(true);
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        console.error("MSAL initialization failed:", error);
        setInitError(message);
      });

    return () => {
      if (callbackId) {
        msalInstance.removeEventCallback(callbackId);
      }
    };
  }, []);

  if (initError) {
    return (
      <div
        role="alert"
        className="flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center"
      >
        <h1 className="text-xl font-semibold text-red-700">
          Échec de l&apos;initialisation de l&apos;authentification
        </h1>
        <p className="text-gray-600">
          Vérifiez la configuration MSAL (variables{" "}
          <code>NEXT_PUBLIC_ENTRA_*</code>).
        </p>
        <pre className="max-w-xl overflow-auto rounded bg-red-50 p-3 text-sm text-red-800">
          {initError}
        </pre>
      </div>
    );
  }

  if (!isReady) {
    return null;
  }

  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
