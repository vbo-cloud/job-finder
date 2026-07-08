import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import CreditsBadge from "@/app/_components/CreditsBadge";
import apiClient from "@/lib/api/client";

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
});
