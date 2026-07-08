import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CVDetailSection from "@/app/_components/CVDetailSection";
import apiClient from "@/lib/api/client";
import type { CVData } from "@/lib/api/types";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    // Covers the matches fetch, the CvAnalysisCard analysis fetch (resolved
    // with a terminal status so no polling timer survives the test), and the
    // thumbnail fetch (skipped anyway: has_thumbnail is false below).
    get: jest.fn((url: string) =>
      url.includes("/analysis")
        ? Promise.resolve({ data: { status: "error", ats_score: null, points_forts: [], points_faibles: [], suggestions: [], coherence_intention: null } })
        : Promise.resolve({ data: { matches: [] } }),
    ),
    patch: jest.fn().mockResolvedValue({}),
    post: jest.fn().mockResolvedValue({}),
  },
}));

const CV: CVData = {
  id: "cv-uuid-1",
  name: "mon-cv.pdf",
  status: "matched",
  uploaded_at: "2026-01-01T00:00:00Z",
  match_count: 0,
  unseen_count: 0,
  has_thumbnail: false,
};

function renderSection() {
  return render(
    <CVDetailSection
      cvs={[CV]}
      selectedCvId={CV.id}
      onCvChange={jest.fn()}
      onClose={jest.fn()}
    />,
  );
}

beforeEach(() => {
  (apiClient.get as jest.Mock).mockClear();
});

describe("CVDetailSection — accordéon d'analyse du CV", () => {
  it("is open by default and renders the analysis panel", async () => {
    renderSection();

    const toggle = screen.getByRole("button", { name: /Analyse de votre CV/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("cv-analysis-panel")).toBeInTheDocument();
    // CvAnalysisCard content is rendered inside the panel
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(`/cv/${CV.id}/analysis`),
    );
  });

  it("collapses when the accordion button is clicked", async () => {
    renderSection();
    // Let the initial matches/analysis fetches resolve before interacting
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(`/matches/cv/${CV.id}`),
    );

    const toggle = screen.getByRole("button", { name: /Analyse de votre CV/i });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("cv-analysis-panel")).not.toBeInTheDocument();
  });
});
