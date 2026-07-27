import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import MatchAnalysisPanel from "@/app/_components/MatchAnalysisPanel";
import apiClient from "@/lib/api/client";
import posthog from "posthog-js";
import type { MatchAnalysisOut } from "@/lib/api/types";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { post: jest.fn().mockResolvedValue({}) },
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: { capture: jest.fn(), identify: jest.fn(), setPersonProperties: jest.fn() },
}));

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
        creditsExhausted={false}
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
        creditsExhausted={false}
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
        creditsExhausted={false}
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
        creditsExhausted={false}
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
        creditsExhausted={false}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.queryByText("Obsolète")).not.toBeInTheDocument();
  });
});

describe("MatchAnalysisPanel — demande de crédits supplémentaires", () => {
  beforeEach(() => {
    (apiClient.post as jest.Mock).mockClear();
    (posthog.capture as jest.Mock).mockClear();
  });

  it("does not show the CTA when creditsExhausted is false", () => {
    render(
      <MatchAnalysisPanel
        analysis={null}
        analysisPending={false}
        analysisError={null}
        creditsExhausted={false}
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.queryByText("Je voudrais plus de crédits")).not.toBeInTheDocument();
  });

  it("shows the CTA alongside the 0-credit error when creditsExhausted is true", () => {
    render(
      <MatchAnalysisPanel
        analysis={null}
        analysisPending={false}
        analysisError="Crédits d'analyse épuisés"
        creditsExhausted
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.getByText("Crédits d'analyse épuisés")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Je voudrais plus de crédits" })).toBeInTheDocument();
  });

  it("posts the request, fires the PostHog event, and swaps to a confirmation on click", async () => {
    render(
      <MatchAnalysisPanel
        analysis={null}
        analysisPending={false}
        analysisError="Crédits d'analyse épuisés"
        creditsExhausted
        onAnalyze={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Je voudrais plus de crédits" }));

    // Optimistic — the confirmation swaps in immediately, without awaiting the API call.
    expect(screen.getByText("Merci, votre demande a été transmise !")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Je voudrais plus de crédits" }),
    ).not.toBeInTheDocument();
    expect(posthog.capture).toHaveBeenCalledWith("more_credits_requested");
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/credits/request-more"));
  });

  it("shows the CTA in the error-status branch too, alongside the credit-exhausted message", () => {
    render(
      <MatchAnalysisPanel
        analysis={{
          status: "error",
          matched_skills: [],
          points_forts: [],
          points_amelioration: [],
          synthese: null,
          verdict: null,
          company_summary: null,
          mission_summary: null,
          why_good_fit_for_user: null,
          why_good_candidate: null,
          score_explanation: null,
          questions_entretien_potentielles: [],
          stale: false,
        }}
        analysisPending={false}
        analysisError="Crédits d'analyse épuisés"
        creditsExhausted
        onAnalyze={jest.fn()}
      />,
    );

    expect(screen.getByText("L'analyse a échoué — vous pouvez la relancer.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Je voudrais plus de crédits" })).toBeInTheDocument();
  });
});
