import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => true,
}));

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    get: (...args: unknown[]) => mockGet(...(args as [])),
    post: (...args: unknown[]) => mockPost(...(args as [])),
  },
}));

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

  it("uploads a selected PDF and refetches the library", async () => {
    mockPost.mockResolvedValue({ data: { cv_id: "new-id" } });
    render(<LibrarySection />);

    await waitFor(() => expect(screen.getByText("cv1.pdf")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledTimes(1);

    const file = new File(["%PDF-1.4"], "new-cv.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith("/cv/upload", expect.any(FormData)));
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
  });

  it("ignores a non-PDF file without calling the upload endpoint", async () => {
    render(<LibrarySection />);
    await waitFor(() => expect(screen.getByText("cv1.pdf")).toBeInTheDocument());

    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(mockPost).not.toHaveBeenCalled();
  });

  it("hides the add-CV slot once the quota is reached", async () => {
    mockGet.mockResolvedValue({
      data: Array.from({ length: 10 }, (_, i) => ({ ...baseCvs[0], id: `cv-${i}` })),
    });
    render(<LibrarySection />);

    await waitFor(() => expect(screen.getAllByText("cv1.pdf")).toHaveLength(10));
    expect(screen.queryByText("Ajouter un CV")).not.toBeInTheDocument();
  });
});
