import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MatchAnalysisPanel from "@/app/_components/MatchAnalysisPanel";
import type { MatchAnalysisOut } from "@/lib/api/types";

function makeAnalysis(overrides: Partial<MatchAnalysisOut> = {}): MatchAnalysisOut {
  return {
    status: "done",
    matched_skills: [],
    points_forts: [],
    points_amelioration: [],
    synthese: "Profil solide.",
    verdict: "À tenter",
    company_summary: null,
    mission_summary: null,
    why_good_fit_for_user: null,
    why_good_candidate: null,
    score_explanation: null,
    questions_entretien_potentielles: [],
    stale: false,
    ...overrides,
  };
}

describe("MatchAnalysisPanel — badge d'analyse obsolète", () => {
  it("does not render the badge when the analysis is not stale", () => {
    render(
      <MatchAnalysisPanel
        analysis={makeAnalysis({ stale: false })}
        analysisPending={false}
        analysisError={null}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  });

  it("renders the badge, tooltip, and retry icon when the analysis is stale", () => {
    render(
      <MatchAnalysisPanel
        analysis={makeAnalysis({ stale: true })}
        analysisPending={false}
        analysisError={null}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.getByText("Obsolète")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Relancer l'analyse de cette offre (consomme 1 crédit)" }),
    ).toBeInTheDocument();
  });

  it("calls onAnalyze (the same paid retry as a fresh analysis) when the retry icon is clicked", () => {
    const onAnalyze = jest.fn();
    render(
      <MatchAnalysisPanel
        analysis={makeAnalysis({ stale: true })}
        analysisPending={false}
        analysisError={null}
        onAnalyze={onAnalyze}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Relancer l'analyse de cette offre (consomme 1 crédit)" }),
    );

    expect(onAnalyze).toHaveBeenCalledTimes(1);
  });

  it("does not render the badge while an analysis is pending/processing, even if the prior stale analysis is still in props", () => {
    render(
      <MatchAnalysisPanel
        analysis={makeAnalysis({ stale: true, status: "done" })}
        analysisPending
        analysisError={null}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
    expect(screen.getByText("Analyse en cours")).toBeInTheDocument();
  });

  it("does not render the badge when status is not done", () => {
    render(
      <MatchAnalysisPanel
        analysis={makeAnalysis({ stale: true, status: "error" })}
        analysisPending={false}
        analysisError={null}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  });
});
