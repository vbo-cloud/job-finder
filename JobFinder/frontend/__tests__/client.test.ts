const mockGetActiveAccount = jest.fn();
const mockGetAllAccounts = jest.fn();
const mockAcquireTokenSilent = jest.fn();
const mockAcquireTokenRedirect = jest.fn();

jest.mock("@/lib/auth/msalInstance", () => ({
  msalInstance: {
    getActiveAccount: () => mockGetActiveAccount(),
    getAllAccounts: () => mockGetAllAccounts(),
    acquireTokenSilent: (...args: unknown[]) => mockAcquireTokenSilent(...args),
    acquireTokenRedirect: (...args: unknown[]) =>
      mockAcquireTokenRedirect(...args),
  },
}));

jest.mock("@/lib/auth/msalConfig", () => ({
  apiTokenRequest: { scopes: ["test-scope"] },
}));

// `redirectInFlight` in client.ts is module-level state, so each test needs a
// fresh module instance (jest.resetModules) to start with the flag unset.
// `InteractionRequiredAuthError` must then be required *after* that reset too
// (not imported statically at the top of this file), otherwise the instance
// thrown here and the class client.ts's `instanceof` check imports would come
// from two different module registrations and never match.
function loadApiClientAndErrorClass() {
  const { InteractionRequiredAuthError } = jest.requireActual<
    typeof import("@azure/msal-browser")
  >("@azure/msal-browser");
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const apiClient = require("@/lib/api/client").default;
  return { apiClient, InteractionRequiredAuthError };
}

// Axios threads the request interceptor through several chained promises
// before invoking it, so a plain `await Promise.resolve()` isn't enough to
// reach our `catch` branch — flush the microtask queue instead.
const flushMicrotasks = () =>
  new Promise((resolve) => setTimeout(resolve, 0));

// Skips axios's real dispatch/XHR step (jsdom has no server to talk to) so
// only the request interceptor under test runs.
const noNetworkAdapter = () => Promise.reject(new Error("no network in tests"));

describe("apiClient request interceptor — single-flight acquireTokenRedirect", () => {
  beforeEach(() => {
    jest.resetModules();
    mockGetActiveAccount.mockReset();
    mockGetAllAccounts.mockReset();
    mockAcquireTokenSilent.mockReset();
    mockAcquireTokenRedirect.mockReset();

    mockGetActiveAccount.mockReturnValue({ homeAccountId: "test-account" });
    mockGetAllAccounts.mockReturnValue([]);
  });

  it("shares a single acquireTokenRedirect call across concurrent requests", async () => {
    const { apiClient, InteractionRequiredAuthError } =
      loadApiClientAndErrorClass();
    mockAcquireTokenSilent.mockRejectedValue(
      new InteractionRequiredAuthError("interaction_required"),
    );

    let resolveRedirect: (() => void) | undefined;
    mockAcquireTokenRedirect.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveRedirect = resolve;
      }),
    );

    const first = apiClient
      .get("/profile", { adapter: noNetworkAdapter })
      .catch(() => undefined);
    const second = apiClient
      .get("/cvs", { adapter: noNetworkAdapter })
      .catch(() => undefined);

    // Let both interceptor callbacks run and hit the InteractionRequiredAuthError branch.
    await flushMicrotasks();
    await flushMicrotasks();

    expect(mockAcquireTokenRedirect).toHaveBeenCalledTimes(1);

    resolveRedirect?.();
    await Promise.all([first, second]);

    expect(mockAcquireTokenRedirect).toHaveBeenCalledTimes(1);
  });

  it("retries acquireTokenRedirect on a later request after a prior redirect attempt failed", async () => {
    const { apiClient, InteractionRequiredAuthError } =
      loadApiClientAndErrorClass();
    mockAcquireTokenSilent.mockRejectedValue(
      new InteractionRequiredAuthError("interaction_required"),
    );
    mockAcquireTokenRedirect.mockRejectedValueOnce(new Error("redirect failed"));

    await apiClient
      .get("/profile", { adapter: noNetworkAdapter })
      .catch(() => undefined);
    expect(mockAcquireTokenRedirect).toHaveBeenCalledTimes(1);

    mockAcquireTokenRedirect.mockResolvedValueOnce(undefined);
    await apiClient
      .get("/cvs", { adapter: noNetworkAdapter })
      .catch(() => undefined);

    expect(mockAcquireTokenRedirect).toHaveBeenCalledTimes(2);
  });
});
