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
  apiTokenRedirectRequest: { scopes: ["test-scope"], prompt: "select_account" },
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
// before invoking it, and our interceptor itself awaits acquireTokenSilent's
// rejection before reaching the catch branch — a plain `await Promise.resolve()`
// only drains one microtask level, not that whole chain. `setTimeout` yields to
// a macrotask instead, and Node/jsdom fully drain the microtask queue (including
// microtasks scheduled by other microtasks) before running any queued macrotask,
// so a single flush is enough regardless of how many promise links are involved.
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

    expect(mockAcquireTokenRedirect).toHaveBeenCalledTimes(1);
    // Confirms client.ts reaches for apiTokenRedirectRequest (which carries
    // `prompt: "select_account"`, forcing the account picker so Entra External
    // ID's buggy auto-reconnect shortcut to the last IdP never triggers — see
    // AADSTS165000) rather than plain apiTokenRequest for this call. The two
    // mocked constants differ only in this field, so this only proves the
    // right constant was picked here, not that apiTokenRequest itself lacks
    // `prompt` — that real guarantee is asserted against the actual module in
    // msalConfig.test.ts.
    expect(mockAcquireTokenRedirect).toHaveBeenCalledWith(
      expect.objectContaining({ prompt: "select_account" }),
    );

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
