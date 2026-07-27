import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => true,
}));

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...(args as [])),
    post: (...args: unknown[]) => mockPost(...(args as [])),
    delete: (...args: unknown[]) => mockDelete(...(args as [])),
  },
}));

// Component import must come after the jest.mock calls above: Jest hoists
// jest.mock to the top of the file regardless of where it's written, but the
// import below is what actually pulls in the module tree that needs mocking —
// keeping it after the mocks here matches evaluation order and avoids the
// temptation to "clean up" by moving it to the top.
import LibrarySection from "@/app/_components/LibrarySection";
import type { CVData } from "@/lib/api/types";

const baseCvs: CVData[] = [
  {
    id: "1",
    name: "cv1.pdf",
    status: "matched",
    uploaded_at: "2024-01-01T00:00:00.000Z",
    match_count: 3,
    unseen_count: 0,
    has_thumbnail: false,
  },
];

// The "Ajouter un CV" slot is new behaviour (previously CVs could only be
// added from the map/orbit section): this test exercises the upload path
// end to end since it can't be reached through the auth-gated live app.
describe("LibrarySection — add CV slot", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockResolvedValue({ data: baseCvs });
  });

  // The add slot no longer owns an upload pipeline: clicking it just asks the
  // parent to open the picker on UploadSection, which is the component that
  // owns validation, the POST, and the fly-down animation (see
  // UploadSection.handleFile). This keeps both entry points on one pipeline.
  it("calls onAddCv when the add slot is clicked", async () => {
    const onAddCv = jest.fn();
    render(<LibrarySection onAddCv={onAddCv} />);

    await waitFor(() => expect(screen.getByText("cv1.pdf")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Ajouter un CV"));

    expect(onAddCv).toHaveBeenCalledTimes(1);
    expect(mockPost).not.toHaveBeenCalled();
  });

  // Regression: onCvsChange must fire on local deletions too, not only on
  // fetches — a stale parent copy kept the CV detail (correspondances) view
  // mounted after the last CV was deleted.
  it("propagates the emptied list to onCvsChange after deleting the last CV", async () => {
    mockDelete.mockResolvedValue({ data: null });
    const onCvsChange = jest.fn();
    render(<LibrarySection onCvsChange={onCvsChange} />);

    await waitFor(() => expect(screen.getByText("cv1.pdf")).toBeInTheDocument());
    expect(onCvsChange).toHaveBeenLastCalledWith(baseCvs);

    fireEvent.click(screen.getByLabelText("Supprimer ce CV"));
    fireEvent.click(screen.getByLabelText("Confirmer la suppression"));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("/cv/1"));
    await waitFor(() => expect(onCvsChange).toHaveBeenLastCalledWith([]));
  });

  it("hides the add-CV slot once the quota is reached", async () => {
    mockGet.mockResolvedValue({
      data: Array.from({ length: 2 }, (_, i) => ({ ...baseCvs[0], id: `cv-${i}` })),
    });
    render(<LibrarySection />);

    await waitFor(() => expect(screen.getAllByText("cv1.pdf")).toHaveLength(2));
    expect(screen.queryByText("Ajouter un CV")).not.toBeInTheDocument();
  });

  // UNLOCKED_CV_SLOTS = 2, TOTAL_LIBRARY_SLOTS = 10: 8 slots stay locked
  // regardless of how many of the 2 unlocked slots are actually filled.
  describe("locked slots (UNLOCKED_CV_SLOTS = 2)", () => {
    const lockedTooltip = "Emplacement non disponible pour le moment";

    it("renders 8 locked slots with 0 real CVs", async () => {
      // 0 confirmed CVs alone leaves the section inaccessible (hidden) — the
      // grid only renders with an optimistic upload in flight, which is the
      // only way to reach a 0-real-CV grid render in this component.
      mockGet.mockResolvedValue({ data: [] });
      render(
        <LibrarySection optimisticUpload={{ thumbnailUrl: "blob:fake", cvId: null }} />,
      );

      await waitFor(() => expect(screen.getAllByTitle(lockedTooltip)).toHaveLength(8));
      expect(screen.getByText("0 / 2")).toBeInTheDocument();
      expect(screen.getByLabelText("Ajouter un CV")).toBeInTheDocument();
    });

    it("renders 8 locked slots with 1 real CV", async () => {
      mockGet.mockResolvedValue({ data: baseCvs });
      render(<LibrarySection />);

      await waitFor(() => expect(screen.getAllByTitle(lockedTooltip)).toHaveLength(8));
      expect(screen.getByText("1 / 2")).toBeInTheDocument();
      expect(screen.getByLabelText("Ajouter un CV")).toBeInTheDocument();
    });

    it("renders 8 locked slots with 2 real CVs and hides the add slot", async () => {
      mockGet.mockResolvedValue({
        data: Array.from({ length: 2 }, (_, i) => ({ ...baseCvs[0], id: `cv-${i}` })),
      });
      render(<LibrarySection />);

      await waitFor(() => expect(screen.getAllByText("cv1.pdf")).toHaveLength(2));
      expect(screen.getAllByTitle(lockedTooltip)).toHaveLength(8);
      expect(screen.getByText("2 / 2")).toBeInTheDocument();
      expect(screen.queryByText("Ajouter un CV")).not.toBeInTheDocument();
    });
  });
});
