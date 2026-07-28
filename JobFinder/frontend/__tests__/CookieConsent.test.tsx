import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";

jest.mock("@/lib/consent/ConsentContext", () => ({
  useConsent: jest.fn(),
}));

import CookieConsent from "@/app/_components/CookieConsent";
import { useConsent } from "@/lib/consent/ConsentContext";

const accept = jest.fn();
const decline = jest.fn();

function mockConsent(overrides: Record<string, unknown> = {}) {
  (useConsent as jest.Mock).mockReturnValue({
    consent: null,
    hydrated: true,
    accept,
    decline,
    reopen: jest.fn(),
    ...overrides,
  });
}

describe("CookieConsent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockConsent();
  });

  it("affiche la barre avec « Accepter » et « Refuser » tant qu'aucun choix n'est fait", () => {
    render(<CookieConsent />);
    expect(screen.getByRole("button", { name: "Accepter" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refuser" })).toBeInTheDocument();
  });

  it("ne s'affiche pas tant que le choix stocké n'est pas chargé (hydrated=false)", () => {
    mockConsent({ hydrated: false });
    render(<CookieConsent />);
    expect(screen.queryByRole("button", { name: "Accepter" })).not.toBeInTheDocument();
  });

  it("ne s'affiche plus une fois un choix fait", () => {
    mockConsent({ consent: "declined" });
    render(<CookieConsent />);
    expect(screen.queryByRole("button", { name: "Accepter" })).not.toBeInTheDocument();
  });

  it("déclenche accept / decline au clic", () => {
    render(<CookieConsent />);

    fireEvent.click(screen.getByRole("button", { name: "Accepter" }));
    expect(accept).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Refuser" }));
    expect(decline).toHaveBeenCalledTimes(1);
  });
});
