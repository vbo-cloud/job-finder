import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MatchItem from "@/app/_components/MatchItem";
import type { MatchOut, RomeCodeEntry } from "@/lib/api/types";

const emptyRomeCodes: Record<string, RomeCodeEntry> = {};

const romeCodesDict: Record<string, RomeCodeEntry> = {
  M1805: { cv_ids: ["cv1"], label: "Études et développement informatique" },
};

function makeMatch(overrides: Partial<MatchOut["offer"]> & { score?: number } = {}): MatchOut {
  const { score = 0.85, ...offerOverrides } = overrides;
  return {
    score,
    offer: {
      id: "offer-uuid-1",
      ft_id: "FT-001",
      title: "Développeur Python",
      company: "ACME",
      location: "Paris (75)",
      contract_type: "CDI",
      salary: null,
      rome_code: "M1805",
      skills: [],
      expires_at: null,
      ...offerOverrides,
    },
  };
}

describe("MatchItem", () => {
  describe("score display", () => {
    it("renders score as percentage", () => {
      render(<MatchItem match={makeMatch({ score: 0.85 })} romeCodesDict={emptyRomeCodes} />);
      expect(screen.getByText("85%")).toBeInTheDocument();
    });

    it("applies success color for score >= 75%", () => {
      render(<MatchItem match={makeMatch({ score: 0.80 })} romeCodesDict={emptyRomeCodes} />);
      const scoreEl = screen.getByText("80%");
      expect(scoreEl).toHaveClass("text-success");
    });

    it("applies warning color for score >= 50% but < 75%", () => {
      render(<MatchItem match={makeMatch({ score: 0.60 })} romeCodesDict={emptyRomeCodes} />);
      const scoreEl = screen.getByText("60%");
      expect(scoreEl).toHaveClass("text-warning");
    });

    it("applies muted color for score < 50%", () => {
      render(<MatchItem match={makeMatch({ score: 0.40 })} romeCodesDict={emptyRomeCodes} />);
      const scoreEl = screen.getByText("40%");
      expect(scoreEl).toHaveClass("text-muted");
    });
  });

  describe("expired offer", () => {
    it("shows 'Expirée' badge when expires_at is in the past", () => {
      render(
        <MatchItem
          match={makeMatch({ expires_at: "2020-01-01T00:00:00Z" })}
          romeCodesDict={emptyRomeCodes}
        />
      );
      expect(screen.getByText("Expirée")).toBeInTheDocument();
    });

    it("does not show expired badge for future offers", () => {
      render(
        <MatchItem
          match={makeMatch({ expires_at: "2099-01-01T00:00:00Z" })}
          romeCodesDict={emptyRomeCodes}
        />
      );
      expect(screen.queryByText("Expirée")).not.toBeInTheDocument();
    });

    it("renders offer title as link when not expired", () => {
      render(<MatchItem match={makeMatch()} romeCodesDict={emptyRomeCodes} />);
      const link = screen.getByRole("link", { name: "Développeur Python" });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", expect.stringContaining("FT-001"));
    });

    it("renders offer title as plain text when expired", () => {
      render(
        <MatchItem
          match={makeMatch({ expires_at: "2020-01-01T00:00:00Z" })}
          romeCodesDict={emptyRomeCodes}
        />
      );
      expect(screen.queryByRole("link", { name: "Développeur Python" })).not.toBeInTheDocument();
      expect(screen.getByText("Développeur Python")).toBeInTheDocument();
    });
  });

  describe("expand / collapse", () => {
    it("is collapsed by default (no tab content visible)", () => {
      render(<MatchItem match={makeMatch()} romeCodesDict={emptyRomeCodes} />);
      expect(screen.queryByText("Offre")).not.toBeInTheDocument();
    });

    it("shows tabs after clicking expand button", () => {
      render(<MatchItem match={makeMatch()} romeCodesDict={emptyRomeCodes} />);
      fireEvent.click(screen.getByRole("button", { name: "Développer" }));
      expect(screen.getByRole("button", { name: "Offre" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Analyse" })).toBeInTheDocument();
    });

    it("shows ROME label from romeCodesDict in offre tab", () => {
      render(<MatchItem match={makeMatch()} romeCodesDict={romeCodesDict} />);
      fireEvent.click(screen.getByRole("button", { name: "Développer" }));
      expect(
        screen.getByText("Études et développement informatique")
      ).toBeInTheDocument();
    });

    it("collapses when clicking expand button again", () => {
      render(<MatchItem match={makeMatch()} romeCodesDict={emptyRomeCodes} />);
      fireEvent.click(screen.getByRole("button", { name: "Développer" }));
      fireEvent.click(screen.getByRole("button", { name: "Réduire" }));
      expect(screen.queryByText("Offre")).not.toBeInTheDocument();
    });
  });
});
