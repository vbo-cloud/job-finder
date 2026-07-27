import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => true,
  useMsal: () => ({
    instance: { loginRedirect: jest.fn() },
  }),
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: { capture: jest.fn() },
}));

jest.mock("@/lib/auth/msalConfig", () => ({
  loginRequest: { scopes: [] },
}));

// Canvas-driven animation, irrelevant to the cap-blocking logic under test —
// jsdom has no 2D canvas context, so this avoids that entirely.
jest.mock("@/app/_components/OrbitAnimation", () => ({
  __esModule: true,
  default: () => null,
}));

import UploadSection, { type UploadSectionHandle } from "@/app/_components/UploadSection";
import apiClient from "@/lib/api/client";

const REJECTION_MESSAGE = "Tous vos emplacements sont occupés";

function pdfFile(name = "cv.pdf"): File {
  return new File(["%PDF-1.4 fake content"], name, { type: "application/pdf" });
}

beforeEach(() => {
  (apiClient.post as jest.Mock).mockReset();
  (apiClient.post as jest.Mock).mockResolvedValue({ data: { cv_id: "new-cv-id" } });
});

describe("UploadSection — CV slot cap", () => {
  describe("below cap (cvCount < UNLOCKED_CV_SLOTS)", () => {
    it("uploads normally on drop", async () => {
      render(<UploadSection cvCount={1} />);
      const dropzone = screen.getByLabelText("Importer un CV");

      await act(async () => {
        fireEvent.drop(dropzone, { dataTransfer: { files: [pdfFile()] } });
        await Promise.resolve();
      });

      expect(apiClient.post).toHaveBeenCalledWith("/cv/upload", expect.any(FormData));
    });

    it("opens the native file picker on click", () => {
      render(<UploadSection cvCount={1} />);
      const clickSpy = jest.spyOn(HTMLInputElement.prototype, "click");

      fireEvent.click(screen.getByLabelText("Importer un CV"));

      expect(clickSpy).toHaveBeenCalledTimes(1);
      clickSpy.mockRestore();
    });

    it("opens the picker via the imperative openPicker handle", () => {
      const ref = React.createRef<UploadSectionHandle>();
      render(<UploadSection ref={ref} cvCount={1} />);
      const clickSpy = jest.spyOn(HTMLInputElement.prototype, "click");

      act(() => ref.current!.openPicker());

      expect(clickSpy).toHaveBeenCalledTimes(1);
      clickSpy.mockRestore();
    });
  });

  describe("at cap (cvCount >= UNLOCKED_CV_SLOTS)", () => {
    it("blocks a drop, shows the rejection message, and never uploads", async () => {
      render(<UploadSection cvCount={2} />);
      const dropzone = screen.getByLabelText("Importer un CV");

      await act(async () => {
        fireEvent.drop(dropzone, { dataTransfer: { files: [pdfFile()] } });
        await Promise.resolve();
      });

      expect(apiClient.post).not.toHaveBeenCalled();
      expect(screen.getByText(REJECTION_MESSAGE)).toBeInTheDocument();
    });

    it("blocks a click without opening the native file picker", () => {
      render(<UploadSection cvCount={2} />);
      const clickSpy = jest.spyOn(HTMLInputElement.prototype, "click");

      fireEvent.click(screen.getByLabelText("Importer un CV"));

      expect(clickSpy).not.toHaveBeenCalled();
      expect(screen.getByText(REJECTION_MESSAGE)).toBeInTheDocument();
      clickSpy.mockRestore();
    });

    it("makes openPicker() a no-op", () => {
      const ref = React.createRef<UploadSectionHandle>();
      render(<UploadSection ref={ref} cvCount={2} />);
      const clickSpy = jest.spyOn(HTMLInputElement.prototype, "click");

      act(() => ref.current!.openPicker());

      expect(clickSpy).not.toHaveBeenCalled();
      expect(screen.getByText(REJECTION_MESSAGE)).toBeInTheDocument();
      clickSpy.mockRestore();
    });
  });
});
