import type { Configuration, RedirectRequest } from "@azure/msal-browser";
import { LogLevel, PromptValue } from "@azure/msal-browser";

/**
 * MSAL configuration for Microsoft Entra External ID (CIAM).
 *
 * Every value is read from `NEXT_PUBLIC_*` environment variables — nothing is
 * hardcoded. These are inlined at build time, so they must be present when
 * `next build` runs (see `.env.local.example`).
 */

// Next.js only inlines NEXT_PUBLIC_* into the client bundle when they are
// referenced statically (process.env.NEXT_PUBLIC_FOO). A dynamic lookup such as
// process.env[name] is NOT replaced at build time, leaving the value undefined
// in the browser. So each variable is read statically and passed in for validation.
function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const clientId = requireEnv(
  "NEXT_PUBLIC_ENTRA_CLIENT_ID",
  process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID,
);
const authority = requireEnv(
  "NEXT_PUBLIC_ENTRA_AUTHORITY",
  process.env.NEXT_PUBLIC_ENTRA_AUTHORITY,
);
const knownAuthority = requireEnv(
  "NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY",
  process.env.NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY,
);
const apiScope = requireEnv(
  "NEXT_PUBLIC_ENTRA_API_SCOPE",
  process.env.NEXT_PUBLIC_ENTRA_API_SCOPE,
);

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

/**
 * Scopes for the silent token flow (`acquireTokenSilent` in
 * `lib/api/client.ts`) — its sole consumer. No `prompt` field: silent
 * acquisition doesn't accept one (no user interaction). Login and the
 * interactive redirect fallback use `loginRequest` / `apiTokenRedirectRequest`
 * below instead, which do carry `prompt`.
 */
export const apiTokenRequest = {
  scopes: [apiScope],
};

/**
 * Login request — requests the API scope so the issued token works against
 * the API. Forces `select_account`: Entra External ID has a known, unfixed
 * bug (AADSTS165000, "Token was not provided") in its auto-reconnect
 * shortcut to the last-used identity provider (Google) for a "keep me signed
 * in" user — the shortcut mishandles the PKCE code_challenge. Forcing the
 * account picker always routes through the normal (working) sign-in path.
 */
export const loginRequest: RedirectRequest = {
  scopes: [apiScope],
  prompt: PromptValue.SELECT_ACCOUNT,
};

/**
 * Request used by the axios interceptor's `acquireTokenRedirect` fallback
 * (`lib/api/client.ts`). Kept distinct from `apiTokenRequest` (used only for
 * the silent flow, `acquireTokenSilent`, which doesn't accept `prompt`) so
 * that constant can stay `prompt`-free. See `loginRequest` above for why
 * `select_account` is forced here too.
 *
 * Value-identical to `loginRequest` today, but kept as its own constant
 * rather than reused: the two cover different call sites (initial sign-in vs.
 * a mid-session reauth triggered by an expired token) that could diverge
 * later — e.g. a `loginHint` added to skip the picker on first login only.
 * Merging them now would couple two call sites that don't inherently need
 * the same request shape.
 */
export const apiTokenRedirectRequest: RedirectRequest = {
  scopes: [apiScope],
  prompt: PromptValue.SELECT_ACCOUNT,
};
