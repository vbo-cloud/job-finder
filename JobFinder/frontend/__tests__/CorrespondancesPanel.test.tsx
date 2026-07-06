import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CorrespondancesPanel from "@/app/_components/CorrespondancesPanel";
import apiClient from "@/lib/api/client";
import type { MatchOut } from "@/lib/api/types";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { patch: jest.fn().mockResolvedValue({}) },
}));

const CV_ID = "cv-uuid-1";
const OFFER_ID = "offer-uuid-1";
const LS_KEY = `jf_seen_${CV_ID}`;

function makeMatch(overrides: Partial<MatchOut> = {}): MatchOut {
  return {
    score: 0.75,
    is_new: true,
    offer: {
      id: OFFER_ID,
      ft_id: "FT-001",
      title: "Ingénieur Cloud",
      company: "ACME",
      location: "Paris",
      contract_type: "CDI",
      description: "Description de test.",
      salary: null,
      rome_code: null,
      skills: [],
      expires_at: null,
    },
    ...overrides,
  };
}

function renderPanel(matches: MatchOut[] = [makeMatch()]) {
  return render(
    <CorrespondancesPanel
      cvId={CV_ID}
      matches={matches}
      loading={false}
      error={null}
    />,
  );
}

beforeEach(() => {
  localStorage.clear();
  (apiClient.patch as jest.Mock).mockClear();
});

describe("CorrespondancesPanel — localStorage contract", () => {
  it("renders without throwing when localStorage entry is corrupted", () => {
    localStorage.setItem(LS_KEY, "not-valid-json{{{");
    // Should not throw — falls back to empty seenIds
    expect(() => renderPanel()).not.toThrow();
    // Offer with is_new=true and no seenIds → badge visible
    expect(screen.getByText("Nouveau")).toBeInTheDocument();
  });

  it("pre-loads seen offer ids from localStorage and hides Nouveau badge", () => {
    localStorage.setItem(LS_KEY, JSON.stringify([OFFER_ID]));
    renderPanel();
    // Offer id is in seenIds → isNew = false → no badge
    expect(screen.queryByText("Nouveau")).not.toBeInTheDocument();
  });

  it("persists offer id to localStorage when a card is first expanded", () => {
    renderPanel();
    expect(localStorage.getItem(LS_KEY)).toBeNull();

    // Click the card header (role=button contains the offer title)
    fireEvent.click(screen.getByRole("button", { name: /Ingénieur Cloud/i }));

    const stored = localStorage.getItem(LS_KEY);
    expect(stored).not.toBeNull();
    const ids = JSON.parse(stored!) as string[];
    expect(ids).toContain(OFFER_ID);
  });

  it("does not duplicate offer id in localStorage on repeated clicks", () => {
    renderPanel();
    const btn = screen.getByRole("button", { name: /Ingénieur Cloud/i });
    fireEvent.click(btn); // open
    fireEvent.click(btn); // close
    fireEvent.click(btn); // re-open

    const ids = JSON.parse(localStorage.getItem(LS_KEY)!) as string[];
    expect(ids.filter((id) => id === OFFER_ID)).toHaveLength(1);
  });
});

describe("CorrespondancesPanel — onMatchSeen callback", () => {
  it("calls onMatchSeen once the seen PATCH resolves, so the library badge can refresh", async () => {
    const onMatchSeen = jest.fn();
    render(
      <CorrespondancesPanel
        cvId={CV_ID}
        matches={[makeMatch()]}
        loading={false}
        error={null}
        onMatchSeen={onMatchSeen}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Ingénieur Cloud/i }));

    await waitFor(() => expect(onMatchSeen).toHaveBeenCalledTimes(1));
  });

  it("does not call onMatchSeen again when the same offer is collapsed and re-expanded", async () => {
    const onMatchSeen = jest.fn();
    render(
      <CorrespondancesPanel
        cvId={CV_ID}
        matches={[makeMatch()]}
        loading={false}
        error={null}
        onMatchSeen={onMatchSeen}
      />,
    );

    const btn = screen.getByRole("button", { name: /Ingénieur Cloud/i });
    fireEvent.click(btn); // open — marks seen
    await waitFor(() => expect(onMatchSeen).toHaveBeenCalledTimes(1));
    fireEvent.click(btn); // close
    fireEvent.click(btn); // re-open — already in seenIds, no new PATCH

    expect(onMatchSeen).toHaveBeenCalledTimes(1);
  });
});

describe("CorrespondancesPanel — stale local cache reconciliation", () => {
  it("retries the seen PATCH when the backend still reports is_new for an offer the local cache already marked handled", async () => {
    // Simulates a previous mark-seen attempt that silently failed server-side
    // (e.g. the CORS misconfiguration): the local cache says "handled" but
    // the backend's is_new is still true — the backend must win, and the
    // PATCH must be retried rather than trusting localStorage forever.
    localStorage.setItem(LS_KEY, JSON.stringify([OFFER_ID]));
    const onMatchSeen = jest.fn();
    render(
      <CorrespondancesPanel
        cvId={CV_ID}
        matches={[makeMatch({ is_new: true })]}
        loading={false}
        error={null}
        onMatchSeen={onMatchSeen}
      />,
    );

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(
        `/cv/${CV_ID}/matches/${OFFER_ID}/seen`,
      ),
    );
    await waitFor(() => expect(onMatchSeen).toHaveBeenCalledTimes(1));
  });

  it("does not retry when the backend already confirms the offer as seen", () => {
    localStorage.setItem(LS_KEY, JSON.stringify([OFFER_ID]));
    render(
      <CorrespondancesPanel
        cvId={CV_ID}
        matches={[makeMatch({ is_new: false })]}
        loading={false}
        error={null}
      />,
    );

    expect(apiClient.patch).not.toHaveBeenCalled();
  });
});
