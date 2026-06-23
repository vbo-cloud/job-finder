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
 * interaction is required, it falls back to a redirect.
 */
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

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
      await msalInstance.acquireTokenRedirect(apiTokenRequest);
    } else {
      throw error;
    }
  }

  return config;
});

export default apiClient;
