// Guards the split between the silent flow (`apiTokenRequest`, used by
// `acquireTokenSilent`, whose type doesn't accept a `prompt` param) and the two
// interactive flows (`loginRequest`, `apiTokenRedirectRequest`) that must
// force `select_account` to avoid Entra External ID's AADSTS165000 bug. Unlike
// the equivalent check in `client.test.ts` (which only sees a hand-written
// mock), this imports the real module so a regression here is caught even if
// nothing changes in `client.ts`.
//
// `.env.local` is intentionally not loaded by Next.js when NODE_ENV=test, and
// msalConfig.ts fail-fasts on missing env vars at import time — so the four
// required vars are set by hand before requiring the real module.
describe("msalConfig prompt fields", () => {
  const ORIGINAL_ENV = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = {
      ...ORIGINAL_ENV,
      NEXT_PUBLIC_ENTRA_CLIENT_ID: "test-client-id",
      NEXT_PUBLIC_ENTRA_AUTHORITY: "https://test.ciamlogin.com/test-tenant",
      NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY: "test.ciamlogin.com",
      NEXT_PUBLIC_ENTRA_API_SCOPE: "api://test/access_as_user",
    };
  });

  afterEach(() => {
    process.env = ORIGINAL_ENV;
  });

  it("does not set prompt on the silent-flow request", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { apiTokenRequest } = require("@/lib/auth/msalConfig");
    expect(apiTokenRequest).not.toHaveProperty("prompt");
  });

  it("forces select_account on both interactive redirect requests", () => {
    const { loginRequest, apiTokenRedirectRequest } =
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require("@/lib/auth/msalConfig");
    expect(loginRequest.prompt).toBe("select_account");
    expect(apiTokenRedirectRequest.prompt).toBe("select_account");
  });
});
