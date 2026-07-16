import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import CreditsBadge from "@/app/_components/CreditsBadge";
import apiClient from "@/lib/api/client";
import { notifyCreditsConsumed, notifyCreditsReleased, notifyCreditsReserved } from "@/lib/creditsBus";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

const mockUseIsAuthenticated = jest.fn();
jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => mockUseIsAuthenticated(),
}));

beforeEach(() => {
  (apiClient.get as jest.Mock).mockReset();
  mockUseIsAuthenticated.mockReset();
});

describe("CreditsBadge", () => {
  it("renders nothing and skips the fetch when not authenticated", () => {
    mockUseIsAuthenticated.mockReturnValue(false);

    const { container } = render(<CreditsBadge />);

    expect(container).toBeEmptyDOMElement();
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("renders the credit count once fetched, linking to /profile", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: { analysis_credits_remaining: 27 },
    });

    render(<CreditsBadge />);

    await waitFor(() => expect(screen.getByText("27")).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/profile");
  });

  it("renders nothing when the user has no profile yet (404)", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock).mockRejectedValue({ response: { status: 404 } });

    render(<CreditsBadge />);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("refetches the balance when a credits-consumed event fires elsewhere in the tree", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock)
      .mockResolvedValueOnce({ data: { analysis_credits_remaining: 30 } })
      .mockResolvedValueOnce({ data: { analysis_credits_remaining: 29 } });

    render(<CreditsBadge />);

    await waitFor(() => expect(screen.getByText("30")).toBeInTheDocument());

    notifyCreditsConsumed();

    await waitFor(() => expect(screen.getByText("29")).toBeInTheDocument());
    expect(apiClient.get).toHaveBeenCalledTimes(2);
  });

  it("decrements the balance optimistically on credits-reserved, without refetching", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock).mockResolvedValueOnce({ data: { analysis_credits_remaining: 10 } });

    render(<CreditsBadge />);
    await waitFor(() => expect(screen.getByText("10")).toBeInTheDocument());

    notifyCreditsReserved();

    await waitFor(() => expect(screen.getByText("9")).toBeInTheDocument());
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it("restores the balance on credits-released after a reservation is rolled back", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock).mockResolvedValueOnce({ data: { analysis_credits_remaining: 10 } });

    render(<CreditsBadge />);
    await waitFor(() => expect(screen.getByText("10")).toBeInTheDocument());

    notifyCreditsReserved();
    await waitFor(() => expect(screen.getByText("9")).toBeInTheDocument());

    notifyCreditsReleased();
    await waitFor(() => expect(screen.getByText("10")).toBeInTheDocument());
  });

  it("does not conjure a phantom credit at 0 balance — a reserve followed by a resync (credits-consumed) settles back at 0", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    (apiClient.get as jest.Mock)
      .mockResolvedValueOnce({ data: { analysis_credits_remaining: 0 } })
      .mockResolvedValueOnce({ data: { analysis_credits_remaining: 0 } });

    render(<CreditsBadge />);
    await waitFor(() => expect(screen.getByText("0")).toBeInTheDocument());

    notifyCreditsReserved(); // clamped — stays at 0
    // A 402 failure resyncs via notifyCreditsConsumed rather than releasing
    // +1, which would otherwise leave the badge at 1 despite 0 real credits.
    notifyCreditsConsumed();

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
