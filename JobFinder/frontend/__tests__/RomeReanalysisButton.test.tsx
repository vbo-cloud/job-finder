import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import RomeReanalysisButton from "@/app/_components/RomeReanalysisButton";
import apiClient from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

const CV_ID = "cv-uuid-1";

beforeEach(() => {
  (apiClient.post as jest.Mock).mockReset();
});

describe("RomeReanalysisButton", () => {
  it("renders the button", () => {
    render(<RomeReanalysisButton cvId={CV_ID} onReanalyzed={jest.fn()} />);

    expect(
      screen.getByRole("button", { name: "Mettre à jour les métiers détectés" }),
    ).toBeInTheDocument();
  });

  it("shows the explanatory tooltip on hover", () => {
    render(<RomeReanalysisButton cvId={CV_ID} onReanalyzed={jest.fn()} />);

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByRole("button").parentElement!);
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Votre description de recherche a changé depuis la dernière analyse de ce CV",
    );
  });

  it("calls the retry endpoint and notifies the parent on success", async () => {
    (apiClient.post as jest.Mock).mockResolvedValue({});
    const onReanalyzed = jest.fn();

    render(<RomeReanalysisButton cvId={CV_ID} onReanalyzed={onReanalyzed} />);
    fireEvent.click(screen.getByRole("button", { name: "Mettre à jour les métiers détectés" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith(`/cv/${CV_ID}/rome/retry`));
    await waitFor(() => expect(onReanalyzed).toHaveBeenCalledTimes(1));
  });

  it("shows an inline error when the retry request fails", async () => {
    (apiClient.post as jest.Mock).mockRejectedValue(new Error("network"));
    const onReanalyzed = jest.fn();

    render(<RomeReanalysisButton cvId={CV_ID} onReanalyzed={onReanalyzed} />);
    fireEvent.click(screen.getByRole("button", { name: "Mettre à jour les métiers détectés" }));

    await waitFor(() =>
      expect(screen.getByText("La mise à jour a échoué — réessayez.")).toBeInTheDocument(),
    );
    expect(onReanalyzed).not.toHaveBeenCalled();
  });
});
