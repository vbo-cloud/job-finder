import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import CvAnalysisCard from "@/app/_components/CvAnalysisCard";
import apiClient from "@/lib/api/client";
import type { CvAnalysisOut } from "@/lib/api/types";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: { capture: jest.fn(), identify: jest.fn(), setPersonProperties: jest.fn() },
}));

const CV_ID = "cv-uuid-1";

function analysis(overrides: Partial<CvAnalysisOut> = {}): CvAnalysisOut {
  return {
    status: "done",
    ats_score: 72,
    synthese: "Un CV bien structuré et lisible.",
    points_forts: ["Structure claire"],
    points_faibles: ["Objectif absent"],
    suggestions: ["Ajouter un titre"],
    coherence_intention: "Cohérent avec le profil.",
    ...overrides,
  };
}

beforeEach(() => {
  (apiClient.get as jest.Mock).mockReset();
  (apiClient.post as jest.Mock).mockReset();
});

describe("CvAnalysisCard", () => {
  it("shows a progress message while pending", async () => {
    (apiClient.get as jest.Mock).mockResolvedValue({ data: analysis({ status: "pending" }) });

    render(<CvAnalysisCard cvId={CV_ID} />);

    await waitFor(() =>
      expect(screen.getByText("Analyse de votre CV en cours…")).toBeInTheDocument(),
    );
  });

  it("renders the ATS score and points when done", async () => {
    (apiClient.get as jest.Mock).mockResolvedValue({ data: analysis() });

    render(<CvAnalysisCard cvId={CV_ID} />);

    await waitFor(() => expect(screen.getByText("72")).toBeInTheDocument());
    expect(screen.getByText("Structure claire")).toBeInTheDocument();
    expect(screen.getByText("Objectif absent")).toBeInTheDocument();
    expect(screen.getByText("Ajouter un titre")).toBeInTheDocument();
    expect(screen.getByText("Cohérent avec le profil.")).toBeInTheDocument();
  });

  it("renders the synthese paragraph above the points lists when done", async () => {
    (apiClient.get as jest.Mock).mockResolvedValue({ data: analysis() });

    render(<CvAnalysisCard cvId={CV_ID} />);

    const synthese = await screen.findByText("Un CV bien structuré et lisible.");
    const pointsForts = screen.getByText("Structure claire");
    expect(
      synthese.compareDocumentPosition(pointsForts) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByText("Synthèse")).toBeInTheDocument();
  });

  it.each([[""], [null]])("omits the synthese block when it is %p", async (value) => {
    (apiClient.get as jest.Mock).mockResolvedValue({ data: analysis({ synthese: value }) });

    render(<CvAnalysisCard cvId={CV_ID} />);

    await waitFor(() => expect(screen.getByText("72")).toBeInTheDocument());
    expect(screen.queryByText("Synthèse")).not.toBeInTheDocument();
  });

  it("shows a silent error message when the fetch itself fails", async () => {
    (apiClient.get as jest.Mock).mockRejectedValue(new Error("network"));

    render(<CvAnalysisCard cvId={CV_ID} />);

    await waitFor(() =>
      expect(screen.getByText("Analyse indisponible pour ce CV")).toBeInTheDocument(),
    );
  });

  describe("error status", () => {
    it("shows the auto-retry message instead of a manual retry button", async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({ data: analysis({ status: "error" }) });

      render(<CvAnalysisCard cvId={CV_ID} />);

      await waitFor(() =>
        expect(screen.getByText(/L'analyse de votre CV a échoué/)).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("button", { name: "Relancer l'analyse" }),
      ).not.toBeInTheDocument();
      expect(apiClient.post).not.toHaveBeenCalled();
    });
  });
});
