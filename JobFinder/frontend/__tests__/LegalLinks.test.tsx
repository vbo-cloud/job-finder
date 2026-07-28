import { render, screen } from "@testing-library/react";
import React from "react";

import LegalLinks from "@/app/_components/LegalLinks";
import { ConsentProvider } from "@/lib/consent/ConsentContext";

// LegalLinks now embeds ManageCookiesButton (a Client island reading the
// consent context), so it must render inside a ConsentProvider.
function renderLegalLinks() {
  return render(
    <ConsentProvider>
      <LegalLinks />
    </ConsentProvider>,
  );
}

describe("LegalLinks — liens légaux globaux", () => {
  it("expose les deux liens pointant vers les bonnes routes", () => {
    renderLegalLinks();

    expect(screen.getByRole("link", { name: "Mentions légales" })).toHaveAttribute(
      "href",
      "/mentions-legales",
    );
    expect(screen.getByRole("link", { name: "Confidentialité" })).toHaveAttribute(
      "href",
      "/confidentialite",
    );
  });

  it("est exposé comme une région de navigation nommée", () => {
    renderLegalLinks();
    expect(
      screen.getByRole("navigation", { name: "Informations légales" }),
    ).toBeInTheDocument();
  });

  it("expose un bouton « Gérer les cookies » (retrait du consentement)", () => {
    renderLegalLinks();
    expect(
      screen.getByRole("button", { name: "Gérer les cookies" }),
    ).toBeInTheDocument();
  });
});
