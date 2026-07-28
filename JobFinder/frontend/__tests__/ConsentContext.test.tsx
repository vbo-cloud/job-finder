import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";

import { ConsentProvider, useConsent } from "@/lib/consent/ConsentContext";

const STORAGE_KEY = "jf-cookie-consent";

function Consumer() {
  const { consent, hydrated, accept, decline, reopen } = useConsent();
  return (
    <div>
      <span data-testid="state">{hydrated ? String(consent) : "loading"}</span>
      <button onClick={accept}>accept</button>
      <button onClick={decline}>decline</button>
      <button onClick={reopen}>reopen</button>
    </div>
  );
}

function renderConsumer() {
  render(
    <ConsentProvider>
      <Consumer />
    </ConsentProvider>,
  );
}

describe("ConsentContext", () => {
  beforeEach(() => localStorage.clear());

  it("démarre sans choix (null) quand rien n'est stocké", () => {
    renderConsumer();
    expect(screen.getByTestId("state")).toHaveTextContent("null");
  });

  it("persiste l'acceptation puis le refus dans localStorage", () => {
    renderConsumer();

    fireEvent.click(screen.getByText("accept"));
    expect(screen.getByTestId("state")).toHaveTextContent("accepted");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("accepted");

    fireEvent.click(screen.getByText("decline"));
    expect(screen.getByTestId("state")).toHaveTextContent("declined");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("declined");
  });

  it("relit un choix déjà stocké au montage", () => {
    localStorage.setItem(STORAGE_KEY, "accepted");
    renderConsumer();
    expect(screen.getByTestId("state")).toHaveTextContent("accepted");
  });

  it("reopen efface le choix stocké (retrait du consentement)", () => {
    localStorage.setItem(STORAGE_KEY, "declined");
    renderConsumer();

    fireEvent.click(screen.getByText("reopen"));
    expect(screen.getByTestId("state")).toHaveTextContent("null");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
