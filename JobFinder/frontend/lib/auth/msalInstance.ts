import { PublicClientApplication } from "@azure/msal-browser";

import { msalConfig } from "./msalConfig";

/**
 * Shared MSAL application instance.
 *
 * A single instance is used by both the React provider (`AuthProvider`) and the
 * axios client interceptor so token acquisition and the in-memory account cache
 * stay consistent. It must be initialized (`await instance.initialize()`) before
 * use — `AuthProvider` handles that.
 */
export const msalInstance = new PublicClientApplication(msalConfig);
