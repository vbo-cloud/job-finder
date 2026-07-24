import React from "react";
import { render } from "@testing-library/react";
import posthog from "posthog-js";
import { PostHogProvider } from "@/app/Providers";

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: {
    init: jest.fn(),
    capture: jest.fn(),
    identify: jest.fn(),
    setPersonProperties: jest.fn(),
  },
}));

jest.mock("posthog-js/react", () => ({
  __esModule: true,
  PostHogProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const ORIGINAL_ENV = process.env;

beforeEach(() => {
  (posthog.init as jest.Mock).mockClear();
  process.env = { ...ORIGINAL_ENV };
});

afterAll(() => {
  process.env = ORIGINAL_ENV;
});

describe("PostHogProvider", () => {
  it("initializes posthog when both env vars are set", () => {
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
    process.env.NEXT_PUBLIC_POSTHOG_HOST = "https://eu.i.posthog.com";

    render(
      <PostHogProvider>
        <div>child</div>
      </PostHogProvider>,
    );

    expect(posthog.init).toHaveBeenCalledWith(
      "phc_test",
      expect.objectContaining({ api_host: "https://eu.i.posthog.com" }),
    );
  });

  // The GitHub repo vars backing these env vars may not exist yet (see
  // docs/JOURNAL.md, PR #221) — this must degrade to "analytics disabled",
  // never crash the root layout that wraps every route.
  it("does not throw and skips init when the env vars are missing", () => {
    delete process.env.NEXT_PUBLIC_POSTHOG_KEY;
    delete process.env.NEXT_PUBLIC_POSTHOG_HOST;
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    expect(() =>
      render(
        <PostHogProvider>
          <div>child</div>
        </PostHogProvider>,
      ),
    ).not.toThrow();
    expect(posthog.init).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("PostHog disabled"));

    warnSpy.mockRestore();
  });
});
