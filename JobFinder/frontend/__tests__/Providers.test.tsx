import React from "react";
import { render } from "@testing-library/react";
import posthog from "posthog-js";

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: {
    init: jest.fn(),
    capture: jest.fn(),
    identify: jest.fn(),
    setPersonProperties: jest.fn(),
    opt_out_capturing: jest.fn(),
    opt_in_capturing: jest.fn(),
    reset: jest.fn(),
  },
}));

jest.mock("posthog-js/react", () => ({
  __esModule: true,
  PostHogProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/lib/consent/ConsentContext", () => ({
  useConsent: jest.fn(),
}));

import { PostHogProvider } from "@/app/Providers";
import { useConsent } from "@/lib/consent/ConsentContext";

const ORIGINAL_ENV = process.env;

function mockConsent(consent: "accepted" | "declined" | null) {
  (useConsent as jest.Mock).mockReturnValue({ consent });
}

beforeEach(() => {
  (posthog.init as jest.Mock).mockClear();
  (posthog.opt_in_capturing as jest.Mock).mockClear();
  (posthog.opt_out_capturing as jest.Mock).mockClear();
  (posthog.reset as jest.Mock).mockClear();
  process.env = { ...ORIGINAL_ENV };
});

afterAll(() => {
  process.env = ORIGINAL_ENV;
});

describe("PostHogProvider — gated on cookie consent", () => {
  it("initializes posthog when consent is accepted and env vars are set", () => {
    mockConsent("accepted");
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

  it("does NOT initialize posthog before a choice is made (consent null)", () => {
    mockConsent(null);
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
    process.env.NEXT_PUBLIC_POSTHOG_HOST = "https://eu.i.posthog.com";

    render(
      <PostHogProvider>
        <div>child</div>
      </PostHogProvider>,
    );

    expect(posthog.init).not.toHaveBeenCalled();
  });

  it("does NOT initialize posthog when consent is declined", () => {
    mockConsent("declined");
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
    process.env.NEXT_PUBLIC_POSTHOG_HOST = "https://eu.i.posthog.com";

    render(
      <PostHogProvider>
        <div>child</div>
      </PostHogProvider>,
    );

    expect(posthog.init).not.toHaveBeenCalled();
  });

  // Even with consent, missing env vars must degrade to "analytics disabled",
  // never crash the root layout that wraps every route (see docs/JOURNAL.md, PR #221).
  it("does not throw and skips init when env vars are missing despite consent", () => {
    mockConsent("accepted");
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

  // Transition on a single mounted provider: accept -> decline -> re-accept.
  // Re-accepting must resume capture via opt_in_capturing() (init() alone is a
  // no-op once opt_out_capturing() has run).
  it("re-enables capturing when the user re-accepts after a decline", () => {
    process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
    process.env.NEXT_PUBLIC_POSTHOG_HOST = "https://eu.i.posthog.com";

    // Fresh element each render so React doesn't bail out on referential
    // equality and actually re-reads the (changed) consent value.
    const ui = () => (
      <PostHogProvider>
        <div>child</div>
      </PostHogProvider>
    );

    mockConsent("accepted");
    const { rerender } = render(ui());
    expect(posthog.init).toHaveBeenCalledTimes(1);

    mockConsent("declined");
    rerender(ui());
    expect(posthog.opt_out_capturing).toHaveBeenCalledTimes(1);
    expect(posthog.reset).toHaveBeenCalledTimes(1);

    mockConsent("accepted");
    rerender(ui());
    // No second init — capture resumes through opt_in_capturing instead.
    expect(posthog.init).toHaveBeenCalledTimes(1);
    expect(posthog.opt_in_capturing).toHaveBeenCalledTimes(1);
  });
});
