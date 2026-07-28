import { render, screen } from "@testing-library/react";
import React from "react";

import LegalLinks from "@/app/_components/LegalLinks";

describe("LegalLinks — liens légaux globaux", () => {
  it("expose les deux liens pointant vers les bonnes routes", () => {
    render(<LegalLinks />);

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
    render(<LegalLinks />);
    expect(
      screen.getByRole("navigation", { name: "Informations légales" }),
    ).toBeInTheDocument();
  });
});
