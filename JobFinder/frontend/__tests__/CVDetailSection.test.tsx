import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CVDetailSection from "@/app/_components/CVDetailSection";
import apiClient from "@/lib/api/client";
import type { CVData, MatchOut } from "@/lib/api/types";

const ANALYSIS_RESPONSE = { status: "error", ats_score: null, points_forts: [], points_faibles: [], suggestions: [], coherence_intention: null };

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    // Covers the matches fetch, the CvAnalysisCard analysis fetch (resolved
    // with a terminal status so no polling timer survives the test), and the
    // thumbnail fetch (skipped anyway: has_thumbnail is false below).
    get: jest.fn((url: string) =>
      url.includes("/analysis")
        ? Promise.resolve({ data: ANALYSIS_RESPONSE })
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
  rome_reanalysis_available: false,
};

function makeMatch(id: string): MatchOut {
  return {
    score: 0.75,
    analysis: null,
    is_new: false,
    offer: {
      id,
      ft_id: id,
      title: `Offre ${id}`,
      company: "ACME",
      location: "Paris (75)",
      contract_type: "CDI",
      description: "",
      salary: null,
      rome_code: null,
      skills: [],
      key_skills: null,
      expires_at: null,
    },
  };
}

function renderSection(cvs: CVData[] = [CV], selectedCvId: string = CV.id) {
  return render(
    <CVDetailSection
      cvs={cvs}
      selectedCvId={selectedCvId}
      onCvChange={jest.fn()}
      onClose={jest.fn()}
    />,
  );
}

function matchesCallCount() {
  return (apiClient.get as jest.Mock).mock.calls.filter(([url]) => url.includes("/matches/cv/")).length;
}

beforeEach(() => {
  (apiClient.get as jest.Mock).mockClear();
  (apiClient.get as jest.Mock).mockImplementation((url: string) =>
    url.includes("/analysis")
      ? Promise.resolve({ data: ANALYSIS_RESPONSE })
      : Promise.resolve({ data: { matches: [] } }),
  );
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

  it("does not collapse after a resize drag on the banner", async () => {
    renderSection();
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(`/matches/cv/${CV.id}`),
    );

    const toggle = screen.getByRole("button", { name: /Analyse de votre CV/i });
    // Drag beyond DRAG_THRESHOLD_PX, then the click the browser fires after
    // pointerup must be swallowed instead of collapsing the panel.
    fireEvent.pointerDown(toggle, { clientY: 300 });
    fireEvent.pointerMove(toggle, { clientY: 250 });
    fireEvent.pointerUp(toggle, { clientY: 250 });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("cv-analysis-panel")).toBeInTheDocument();
  });

  it("still collapses on a press-and-release without movement", async () => {
    renderSection();
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(`/matches/cv/${CV.id}`),
    );

    const toggle = screen.getByRole("button", { name: /Analyse de votre CV/i });
    fireEvent.pointerDown(toggle, { clientY: 300 });
    fireEvent.pointerUp(toggle, { clientY: 300 });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});

describe("CVDetailSection — bouton de ré-analyse ROME", () => {
  it("is not rendered when rome_reanalysis_available is false", async () => {
    renderSection();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith(`/matches/cv/${CV.id}`));

    expect(
      screen.queryByRole("button", { name: "Mettre à jour les métiers détectés" }),
    ).not.toBeInTheDocument();
  });

  it("is rendered and wired to onRomeReanalyzed when rome_reanalysis_available is true", async () => {
    const cv = { ...CV, rome_reanalysis_available: true };
    (apiClient.post as jest.Mock).mockResolvedValue({});
    const onRomeReanalyzed = jest.fn();
    render(
      <CVDetailSection
        cvs={[cv]}
        selectedCvId={cv.id}
        onCvChange={jest.fn()}
        onClose={jest.fn()}
        onRomeReanalyzed={onRomeReanalyzed}
      />,
    );
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith(`/matches/cv/${cv.id}`));

    fireEvent.click(screen.getByRole("button", { name: "Mettre à jour les métiers détectés" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith(`/cv/${cv.id}/rome/retry`));
    await waitFor(() => expect(onRomeReanalyzed).toHaveBeenCalledTimes(1));
  });
});

describe("CVDetailSection — rafraîchissement des correspondances quand match_count change", () => {
  it("refetches matches when match_count changes without selectedCvId or zoneVersion changing", async () => {
    let matchesCall = 0;
    (apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes("/analysis")) return Promise.resolve({ data: ANALYSIS_RESPONSE });
      matchesCall += 1;
      return Promise.resolve({ data: { matches: matchesCall === 1 ? [] : [makeMatch("o1"), makeMatch("o2")] } });
    });

    const { rerender } = renderSection();
    await waitFor(() => expect(matchesCallCount()).toBe(1));

    rerender(
      <CVDetailSection
        cvs={[{ ...CV, match_count: 2 }]}
        selectedCvId={CV.id}
        onCvChange={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    await waitFor(() => expect(matchesCallCount()).toBe(2));
    expect(await screen.findByText("2 correspondances analysées")).toBeInTheDocument();
  });

  it("does not refetch matches when an unrelated prop changes with the same match_count", async () => {
    const { rerender } = renderSection();
    await waitFor(() => expect(matchesCallCount()).toBe(1));

    // New array/object references, same match_count value — the effect must
    // key off the value, not the identity of the `cvs` array.
    rerender(
      <CVDetailSection
        cvs={[{ ...CV }]}
        selectedCvId={CV.id}
        onCvChange={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    // Give any accidental effect a tick to fire before asserting it didn't.
    await new Promise((r) => setTimeout(r, 0));
    expect(matchesCallCount()).toBe(1);
  });

  it("keeps the displayed matches and shows no error when the silent refresh fails", async () => {
    let matchesCall = 0;
    (apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes("/analysis")) return Promise.resolve({ data: ANALYSIS_RESPONSE });
      matchesCall += 1;
      return matchesCall === 1
        ? Promise.resolve({ data: { matches: [makeMatch("o1")] } })
        : Promise.reject(new Error("network down"));
    });

    const { rerender } = renderSection();
    await waitFor(() => expect(screen.getByText("1 correspondances analysées")).toBeInTheDocument());

    rerender(
      <CVDetailSection
        cvs={[{ ...CV, match_count: 2 }]}
        selectedCvId={CV.id}
        onCvChange={jest.fn()}
        onClose={jest.fn()}
      />,
    );

    await waitFor(() => expect(matchesCallCount()).toBe(2));
    expect(screen.getByText("1 correspondances analysées")).toBeInTheDocument();
    expect(screen.queryByText(/impossible de charger les matchs/i)).not.toBeInTheDocument();
  });
});
