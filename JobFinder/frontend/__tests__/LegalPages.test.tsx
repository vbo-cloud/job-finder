import { render, screen } from "@testing-library/react";
import React from "react";

import ConfidentialitePage from "@/app/confidentialite/page";
import MentionsLegalesPage from "@/app/mentions-legales/page";

// Both pages are pure static Server Components (no auth, no data fetch), so
// they render with no mocks — mirroring their "reachable while logged out"
// requirement.
describe("Page /mentions-legales", () => {
  it("rend le titre et les mentions légales attendues", () => {
    render(<MentionsLegalesPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Mentions légales" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Éditeur" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Hébergement" })).toBeInTheDocument();
    expect(screen.getByText("SIREN 327 733 184")).toBeInTheDocument();
    expect(screen.getByText("Contact : legal@vincentboutin.dev")).toBeInTheDocument();
    expect(
      screen.getByText(/loi n° 2004-575 du 21 juin 2004 pour la confiance dans l'économie numérique/),
    ).toBeInTheDocument();
  });

  it("expose un lien de retour vers l'accueil", () => {
    render(<MentionsLegalesPage />);
    expect(screen.getByRole("link", { name: "Accueil" })).toHaveAttribute("href", "/");
  });
});

describe("Page /confidentialite", () => {
  it("rend le titre et les rubriques RGPD attendues", () => {
    render(<ConfidentialitePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Politique de confidentialité" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Responsable du traitement" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Droits des utilisateurs" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/CNIL/)).toBeInTheDocument();
  });

  it("mentionne Azure OpenAI mais n'ajoute pas de destinataire « OpenAI » distinct", () => {
    render(<ConfidentialitePage />);

    // La ligne « Microsoft Azure » couvre déjà le service Azure OpenAI (service
    // Microsoft, jamais OpenAI Inc. ; traitement dans la zone de données UE de
    // Microsoft depuis la PR #263). Une entrée « OpenAI » séparée serait fausse.
    expect(
      screen.getByText(/Microsoft Azure \(service Azure OpenAI/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^OpenAI/)).not.toBeInTheDocument();
  });
});
