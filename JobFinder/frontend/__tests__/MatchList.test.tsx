import React from "react";
import { render, screen } from "@testing-library/react";
import MatchList from "@/app/_components/MatchList";
import type { MatchOut, RomeCodeEntry } from "@/lib/api/types";

const emptyRomeCodes: Record<string, RomeCodeEntry> = {};

function makeMatch(id: string, score = 0.8): MatchOut {
  return {
    score,
    offer: {
      id,
      ft_id: `FT-${id}`,
      title: `Offre ${id}`,
      company: "ACME",
      location: "Paris",
      contract_type: "CDI",
      salary: null,
      rome_code: null,
      skills: [],
      expires_at: null,
    },
  };
}

describe("MatchList", () => {
  it("renders skeleton placeholders when loading", () => {
    const { container } = render(
      <MatchList matches={[]} loading={true} romeCodesDict={emptyRomeCodes} />
    );
    // 5 skeleton divs with animate-pulse class
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons).toHaveLength(5);
  });

  it("shows empty state message when no matches and not loading", () => {
    render(
      <MatchList matches={[]} loading={false} romeCodesDict={emptyRomeCodes} />
    );
    expect(screen.getByText("Aucun match trouvé")).toBeInTheDocument();
  });

  it("renders a MatchItem for each match", () => {
    const matches = [makeMatch("1"), makeMatch("2"), makeMatch("3")];
    render(
      <MatchList
        matches={matches}
        loading={false}
        romeCodesDict={emptyRomeCodes}
      />
    );
    expect(screen.getByText("Offre 1")).toBeInTheDocument();
    expect(screen.getByText("Offre 2")).toBeInTheDocument();
    expect(screen.getByText("Offre 3")).toBeInTheDocument();
  });

  it("does not show empty state when matches are present", () => {
    render(
      <MatchList
        matches={[makeMatch("1")]}
        loading={false}
        romeCodesDict={emptyRomeCodes}
      />
    );
    expect(screen.queryByText("Aucun match trouvé")).not.toBeInTheDocument();
  });

  it("does not show empty state when still loading (even if matches array is empty)", () => {
    render(
      <MatchList matches={[]} loading={true} romeCodesDict={emptyRomeCodes} />
    );
    expect(screen.queryByText("Aucun match trouvé")).not.toBeInTheDocument();
  });
});
