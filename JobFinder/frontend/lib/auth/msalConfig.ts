import type { Configuration, RedirectRequest } from "@azure/msal-browser";
import { LogLevel } from "@azure/msal-browser";

/**
 * MSAL configuration for Microsoft Entra External ID (CIAM).
 *
 * Every value is read from `NEXT_PUBLIC_*` environment variables — nothing is
 * hardcoded. These are inlined at build time, so they must be present when
 * `next build` runs (see `.env.local.example`).
 */

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const clientId = requireEnv("NEXT_PUBLIC_ENTRA_CLIENT_ID");
const authority = requireEnv("NEXT_PUBLIC_ENTRA_AUTHORITY");
const knownAuthority = requireEnv("NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY");
const apiScope = requireEnv("NEXT_PUBLIC_ENTRA_API_SCOPE");

// Defaults to the current origin in the browser; falls back to the env var
// for SSR / build contexts where `window` is unavailable.
const redirectUri =
  process.env.NEXT_PUBLIC_REDIRECT_URI ??
  (typeof window !== "undefined" ? window.location.origin : undefined);

export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority,
    knownAuthorities: [knownAuthority],
    redirectUri,
    postLogoutRedirectUri: redirectUri,
  },
  cache: {
    // sessionStorage scopes tokens to the tab and avoids persisting them to
    // localStorage — acceptable for a portfolio SPA with Bearer-token auth.
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      loggerCallback: () => {
        // No-op: MSAL logs are silenced by default. Wire to console in dev if needed.
      },
    },
  },
};

/** Scopes requested at login and when calling the FastAPI backend. */
export const apiTokenRequest = {
  scopes: [apiScope],
};

/** Login request — requests the API scope so the issued token works against the API. */
export const loginRequest: RedirectRequest = {
  scopes: [apiScope],
};
