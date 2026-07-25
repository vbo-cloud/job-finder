import { InteractionRequiredAuthError } from "@azure/msal-browser";
import axios from "axios";

import { apiTokenRequest } from "@/lib/auth/msalConfig";
import { msalInstance } from "@/lib/auth/msalInstance";

/**
 * Axios client for the FastAPI backend.
 *
 * A request interceptor acquires an access token via MSAL
 * (`acquireTokenSilent`, scoped to `NEXT_PUBLIC_ENTRA_API_SCOPE`) and injects it
 * as `Authorization: Bearer <token>`. When the silent flow fails because user
 * interaction is required, it falls back to a redirect — deduplicated
 * single-flight across concurrent callers (see `redirectInFlight` below) so
 * that two components mounting together don't each trigger their own
 * `acquireTokenRedirect` and corrupt each other's OAuth state/nonce.
 */
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

let redirectInFlight: Promise<void> | null = null;

apiClient.interceptors.request.use(async (config) => {
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // No signed-in account: send the request unauthenticated. The backend
  // returns 401 and the UI can prompt for sign-in.
  if (!account) {
    return config;
  }

  try {
    const result = await msalInstance.acquireTokenSilent({
      ...apiTokenRequest,
      account,
    });
    config.headers.Authorization = `Bearer ${result.accessToken}`;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      // Single-flight : si une redirection MSAL est déjà en cours (déclenchée
      // par un autre appel concurrent de l'intercepteur — ex. CreditsBadge et
      // LibrarySection montés ensemble), on attend celle-ci au lieu d'en
      // démarrer une seconde. Deux `acquireTokenRedirect` concurrents
      // corrompent le state/nonce OAuth partagé en sessionStorage et font
      // échouer le retour de la CIAM (bug reproductible : reconnexion après
      // fermeture du navigateur).
      if (!redirectInFlight) {
        redirectInFlight = msalInstance
          .acquireTokenRedirect(apiTokenRequest)
          .catch((redirectError) => {
            redirectInFlight = null;
            throw redirectError;
          });
      }
      await redirectInFlight;
    } else {
      throw error;
    }
  }

  return config;
});

export default apiClient;
