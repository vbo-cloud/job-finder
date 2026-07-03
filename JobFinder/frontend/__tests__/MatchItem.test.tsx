import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MatchItem, { type MatchItemData } from "@/app/_components/MatchItem";
import type { MatchOut } from "@/lib/api/types";

function makeMatch(
  score = 0.85,
  offerOverrides: Partial<MatchOut["offer"]> = {},
): MatchOut {
  return {
    score,
    is_new: false,
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

function makeProps(overrides: Partial<MatchItemData> = {}): MatchItemData {
  return {
    match: makeMatch(),
    isNew: false,
    isSaved: false,
    isApplied: false,
    isExpanded: false,
    onSelect: jest.fn(),
    onSave: jest.fn(),
    onApply: jest.fn(),
    onReject: jest.fn(),
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
    it("shows Postuler when not applied", () => {
      render(<MatchItem {...makeProps({ isExpanded: true, isApplied: false })} />);
      expect(screen.getByRole("button", { name: "Postuler" })).toBeInTheDocument();
    });

    it("shows Candidature envoyée when applied", () => {
      render(<MatchItem {...makeProps({ isExpanded: true, isApplied: true })} />);
      expect(screen.getByText("Candidature envoyée ✓")).toBeInTheDocument();
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

    it("shows description text in offre tab", () => {
      render(
        <MatchItem
          match={makeMatch(0.85, { description: "Texte complet\nde l'offre." })}
          romeCodesDict={emptyRomeCodes}
        />
      );
      fireEvent.click(screen.getByRole("button", { name: "Développer" }));
      expect(screen.getByText(/Texte complet/)).toBeInTheDocument();
    });
  });
});
