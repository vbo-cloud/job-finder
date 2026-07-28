"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import { loginRequest } from "@/lib/auth/msalConfig";

/**
 * Minimal sign-in / sign-out control.
 *
 * Triggers an MSAL redirect login and reflects the current authentication
 * state. This is the only interactive element of the walking skeleton.
 */
export function LoginButton() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const handleLogin = () => {
    void instance.loginRedirect(loginRequest);
  };

  const handleLogout = () => {
    void instance.logoutRedirect();
  };

  if (isAuthenticated) {
    const activeAccount = instance.getActiveAccount() ?? accounts[0];
    const claims = activeAccount?.idTokenClaims as Record<string, unknown> | undefined;
    const preferredUsername = claims?.preferred_username as string | undefined;
    const displayName = claims?.name as string | undefined;
    const name =
      preferredUsername ??
      (displayName && displayName !== "unknown" ? displayName : undefined) ??
      "Connecté";
    return (
      <div className="flex flex-col items-center gap-3">
        <p className="text-green-700">Connecté en tant que {name}</p>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded bg-gray-800 px-4 py-2 text-white hover:bg-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          Se déconnecter
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <p className="text-gray-500">Non connecté</p>
      <button
        type="button"
        onClick={handleLogin}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        Se connecter
      </button>
    </div>
  );
}
