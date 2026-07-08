import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminRefillButton from "@/app/profile/_components/AdminRefillButton";
import apiClient from "@/lib/api/client";
import { onCreditsConsumed } from "@/lib/creditsBus";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    post: jest.fn(),
  },
}));

beforeEach(() => {
  (apiClient.post as jest.Mock).mockReset();
});

describe("AdminRefillButton", () => {
  it("posts the refill, reports the new balance and notifies the credits bus", async () => {
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: { analysis_credits_remaining: 40 },
    });
    const onRefilled = jest.fn();
    const onBusNotified = jest.fn();
    const unsubscribe = onCreditsConsumed(onBusNotified);

    render(<AdminRefillButton onRefilled={onRefilled} />);
    fireEvent.click(screen.getByRole("button", { name: "+10 crédits" }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/profile/credits/refill"),
    );
    await waitFor(() => expect(onRefilled).toHaveBeenCalledWith(40));
    expect(onBusNotified).toHaveBeenCalledTimes(1);

    unsubscribe();
  });

  it("shows an error and does not report a balance when the request fails", async () => {
    (apiClient.post as jest.Mock).mockRejectedValue(new Error("403"));
    const onRefilled = jest.fn();

    render(<AdminRefillButton onRefilled={onRefilled} />);
    fireEvent.click(screen.getByRole("button", { name: "+10 crédits" }));

    await waitFor(() =>
      expect(screen.getByText("Erreur, réessayez")).toBeInTheDocument(),
    );
    expect(onRefilled).not.toHaveBeenCalled();
  });
});
