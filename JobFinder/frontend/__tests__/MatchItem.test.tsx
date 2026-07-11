import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MatchItem, { type MatchItemData } from "@/app/_components/MatchItem";
import type { MatchAnalysisOut, MatchOut } from "@/lib/api/types";

function makeMatch(
  score = 0.85,
  offerOverrides: Partial<MatchOut["offer"]> = {},
  analysis: MatchAnalysisOut | null = null,
): MatchOut {
  return {
    score,
    is_new: false,
    analysis,
    offer: {
      id: "offer-uuid-1",
      ft_id: "FT-001",
      title: "Développeur Python",
      company: "ACME",
      location: "Paris (75)",
      contract_type: "CDI",
      description: "Description complète de l'offre.",
      salary: null,
      rome_code: "M1805",
      skills: [],
      expires_at: null,
      ...offerOverrides,
    },
  };
}

function makeAnalysis(overrides: Partial<MatchAnalysisOut> = {}): MatchAnalysisOut {
  return {
    status: "done",
    matched_skills: ["Python", "Docker", "Azure", "Terraform"],
    points_forts: ["Expérience solide en Python"],
    points_amelioration: [
      { constat: "Certifications cloud absentes", suggestion_concrete: "Passer la certification AZ-104." },
    ],
    synthese: "Profil solide sur les compétences cœur — un point à travailler avant de postuler.",
    verdict: "À tenter",
    company_summary: null,
    mission_summary: "Développement backend Python.",
    why_good_fit_for_user: "Poste aligné avec votre recherche cloud.",
    why_good_candidate: "4 ans d'expérience Python.",
    score_explanation: "Forte couverture des compétences demandées.",
    questions_entretien_potentielles: ["Comment gérez-vous les migrations ?"],
    ...overrides,
  };
}

function makeProps(overrides: Partial<MatchItemData> = {}): MatchItemData {
  return {
    match: makeMatch(),
    isNew: false,
    isSaved: false,
    isExpanded: false,
    analysisPending: false,
    onSelect: jest.fn(),
    onSave: jest.fn(),
    onReject: jest.fn(),
    onAnalyze: jest.fn(),
    ...overrides,
  };
}

describe("MatchItem", () => {
  describe("score display", () => {
    it("renders score as percentage", () => {
      render(<MatchItem {...makeProps({ match: makeMatch(0.85) })} />);
      expect(screen.getByText("85%")).toBeInTheDocument();
    });

    it("renders different score values correctly", () => {
      render(<MatchItem {...makeProps({ match: makeMatch(0.60) })} />);
      expect(screen.getByText("60%")).toBeInTheDocument();
    });
  });

  describe("offer title", () => {
    it("renders offer title as FT link", () => {
      render(<MatchItem {...makeProps()} />);
      const link = screen.getByRole("link", { name: "Développeur Python" });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", expect.stringContaining("FT-001"));
    });
  });

  describe("Nouveau pill", () => {
    it("shows Nouveau pill when isNew is true", () => {
      render(<MatchItem {...makeProps({ isNew: true })} />);
      expect(screen.getByText("Nouveau")).toBeInTheDocument();
    });

    it("hides Nouveau pill when isNew is false", () => {
      render(<MatchItem {...makeProps({ isNew: false })} />);
      expect(screen.queryByText("Nouveau")).not.toBeInTheDocument();
    });
  });

  describe("accordion", () => {
    it("does not show accordion content when not expanded", () => {
      render(<MatchItem {...makeProps({ isExpanded: false })} />);
      expect(screen.queryByText(/Descriptif de l.offre/)).not.toBeInTheDocument();
    });

    it("shows accordion content when expanded", () => {
      render(<MatchItem {...makeProps({ isExpanded: true })} />);
      expect(screen.getByText(/Descriptif de l.offre/)).toBeInTheDocument();
      expect(screen.getByText(/Review de l.agent/)).toBeInTheDocument();
    });

    it("calls onSelect when the card row is clicked", () => {
      const onSelect = jest.fn();
      render(<MatchItem {...makeProps({ onSelect })} />);
      // company name is inside the clickable row (no stopPropagation there)
      fireEvent.click(screen.getByText("ACME"));
      expect(onSelect).toHaveBeenCalledTimes(1);
    });
  });

  describe("actions in accordion", () => {
    it("shows a Consulter l'offre link pointing at the FT offer page", () => {
      render(<MatchItem {...makeProps({ isExpanded: true })} />);
      const link = screen.getByRole("link", { name: "Consulter l'offre" });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", expect.stringContaining("FT-001"));
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("calls onReject when Rejeter is clicked", () => {
      const onReject = jest.fn();
      render(<MatchItem {...makeProps({ isExpanded: true, onReject })} />);
      fireEvent.click(screen.getByRole("button", { name: "Rejeter" }));
      expect(onReject).toHaveBeenCalledTimes(1);
    });
  });

  describe("bookmark", () => {
    it("calls onSave when bookmark is clicked", () => {
      const onSave = jest.fn();
      render(<MatchItem {...makeProps({ onSave })} />);
      fireEvent.click(screen.getByRole("button", { name: "Sauvegarder" }));
      expect(onSave).toHaveBeenCalledTimes(1);
    });

    it("shows Retirer des favoris label when saved", () => {
      render(<MatchItem {...makeProps({ isSaved: true })} />);
      expect(screen.getByRole("button", { name: "Retirer des favoris" })).toBeInTheDocument();
    });

    it("shows salary in expanded view", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, { salary: "40 000 € brut" }),
        })} />
      );
      expect(screen.getByText("40 000 € brut")).toBeInTheDocument();
    });

    it("renders offer description in expanded view", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, { description: "Texte complet\nde l'offre." }),
        })} />
      );
      expect(screen.getByText(/Texte complet/)).toBeInTheDocument();
    });
  });

  describe("search highlight in description", () => {
    it("wraps a matching substring of the description in a <mark>", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          searchQuery: "azure",
          match: makeMatch(0.85, { description: "Déploiement Azure avec Terraform." }),
        })} />
      );
      const mark = screen.getByText("Azure");
      expect(mark.tagName).toBe("MARK");
    });

    it("renders the description as plain text when there is no search query", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, { description: "Déploiement Azure avec Terraform." }),
        })} />
      );
      expect(screen.getByText(/Déploiement Azure avec Terraform/)).toBeInTheDocument();
      expect(document.querySelector("mark")).not.toBeInTheDocument();
    });

    it("does not highlight when the query does not appear in the description", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          searchQuery: "kubernetes",
          match: makeMatch(0.85, { description: "Déploiement Azure avec Terraform." }),
        })} />
      );
      expect(document.querySelector("mark")).not.toBeInTheDocument();
    });
  });

  describe("matched skills badges (compact view)", () => {
    it("shows up to 3 matched_skills badges when an analysis is done", () => {
      render(
        <MatchItem {...makeProps({ match: makeMatch(0.85, {}, makeAnalysis()) })} />
      );
      expect(screen.getByText("Python")).toBeInTheDocument();
      expect(screen.getByText("Docker")).toBeInTheDocument();
      expect(screen.getByText("Azure")).toBeInTheDocument();
      // 4th skill is cut by the slice(0, 3)
      expect(screen.queryByText("Terraform")).not.toBeInTheDocument();
    });

    it("shows no badge when there is no analysis", () => {
      render(<MatchItem {...makeProps()} />);
      expect(screen.queryByText("Python")).not.toBeInTheDocument();
    });
  });

  describe("agent review column", () => {
    it("shows the analyze button when no analysis exists", () => {
      render(<MatchItem {...makeProps({ isExpanded: true })} />);
      expect(
        screen.getByRole("button", { name: "Analyser cette offre avec l'IA" })
      ).toBeInTheDocument();
    });

    it("calls onAnalyze when the analyze button is clicked", () => {
      const onAnalyze = jest.fn();
      render(<MatchItem {...makeProps({ isExpanded: true, onAnalyze })} />);
      fireEvent.click(screen.getByRole("button", { name: "Analyser cette offre avec l'IA" }));
      expect(onAnalyze).toHaveBeenCalledTimes(1);
    });

    it("shows a disabled in-progress button while analysisPending", () => {
      render(<MatchItem {...makeProps({ isExpanded: true, analysisPending: true })} />);
      const btn = screen.getByRole("button", { name: "Analyse en cours…" });
      expect(btn).toBeDisabled();
    });

    it("shows a disabled in-progress button when the analysis is processing", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, {}, makeAnalysis({ status: "processing" })),
        })} />
      );
      expect(screen.getByRole("button", { name: "Analyse en cours…" })).toBeDisabled();
    });

    it("renders synthese, points forts and points d'amélioration when done", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, {}, makeAnalysis()),
        })} />
      );
      // synthese shows twice: compact teaser line + expanded review panel
      expect(screen.getAllByText(/Profil solide sur les compétences cœur/)).toHaveLength(2);
      expect(screen.getByText("Expérience solide en Python")).toBeInTheDocument();
      // constat renders as the main line, suggestion_concrete as a secondary line below it
      expect(screen.getByText("Certifications cloud absentes")).toBeInTheDocument();
      expect(screen.getByText("Passer la certification AZ-104.")).toBeInTheDocument();
    });

    it("renders the enriched fields when done", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, {}, makeAnalysis()),
        })} />
      );
      expect(screen.getByText("À tenter")).toBeInTheDocument();
      expect(screen.getByText("Développement backend Python.")).toBeInTheDocument();
      expect(screen.getByText("Poste aligné avec votre recherche cloud.")).toBeInTheDocument();
      expect(screen.getByText("4 ans d'expérience Python.")).toBeInTheDocument();
      expect(screen.getByText("Forte couverture des compétences demandées.")).toBeInTheDocument();
      expect(screen.getByText("Comment gérez-vous les migrations ?")).toBeInTheDocument();
      // company_summary is null in the fixture → its section is not rendered
      expect(screen.queryByText("Entreprise")).not.toBeInTheDocument();
    });

    it("renders only the constat when suggestion_concrete is null (legacy rows)", () => {
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          match: makeMatch(0.85, {}, makeAnalysis({
            points_amelioration: [{ constat: "Certifications cloud absentes", suggestion_concrete: null }],
          })),
        })} />
      );
      expect(screen.getByText("Certifications cloud absentes")).toBeInTheDocument();
      expect(screen.queryByText("→")).not.toBeInTheDocument();
    });

    it("shows a retry button mentioning the credit cost on error", () => {
      const onAnalyze = jest.fn();
      render(
        <MatchItem {...makeProps({
          isExpanded: true,
          onAnalyze,
          match: makeMatch(0.85, {}, makeAnalysis({ status: "error" })),
        })} />
      );
      const btn = screen.getByRole("button", { name: /consomme 1 crédit/ });
      fireEvent.click(btn);
      expect(onAnalyze).toHaveBeenCalledTimes(1);
    });
  });
});
