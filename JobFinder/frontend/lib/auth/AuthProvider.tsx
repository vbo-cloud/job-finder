"use client";

import { EventType } from "@azure/msal-browser";
import type { AuthenticationResult } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import { useEffect, useState } from "react";

import { msalInstance } from "./msalInstance";

/**
 * Wraps the application in an initialized `MsalProvider`.
 *
 * MSAL v3 requires `initialize()` to be awaited before any other API call, so
 * the children are gated until initialization completes. A login-success event
 * callback promotes the authenticated account to the active account.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let callbackId: string | null = null;

    msalInstance.initialize().then(() => {
      const accounts = msalInstance.getAllAccounts();
      if (accounts.length > 0 && !msalInstance.getActiveAccount()) {
        msalInstance.setActiveAccount(accounts[0]);
      }

      callbackId = msalInstance.addEventCallback((event) => {
        if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
          const result = event.payload as AuthenticationResult;
          msalInstance.setActiveAccount(result.account);
        }
      });

      setIsReady(true);
    });

    return () => {
      if (callbackId) {
        msalInstance.removeEventCallback(callbackId);
      }
    };
  }, []);

  if (!isReady) {
    return null;
  }

  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
