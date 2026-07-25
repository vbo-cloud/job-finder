import React from "react";
import { render, screen } from "@testing-library/react";

const mockUseIsAuthenticated = jest.fn();
jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => mockUseIsAuthenticated(),
}));

// The real client pulls in msalConfig, which fails fast on missing
// NEXT_PUBLIC_ENTRA_CLIENT_ID — irrelevant here since nothing in this test
// exercises an actual API call.
jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

// HomeClient's other sections (map, library, CV detail) are heavy — leaflet,
// react-dropzone, apiClient fetches — and irrelevant to what this test
// covers, so they're stubbed out to isolate LeftNavRail's auth gating.
jest.mock("@/app/_components/HomeMapSection", () => ({
  __esModule: true,
  default: React.forwardRef(function HomeMapSectionStub(_props: unknown, _ref: unknown) {
    return <div data-testid="home-map-section-stub" />;
  }),
}));
jest.mock("@/app/_components/LibrarySection", () => ({
  __esModule: true,
  default: () => <div data-testid="library-section-stub" />,
}));

// Component import must come after the jest.mock calls above: Jest hoists
// jest.mock to the top of the file regardless of where it's written, but the
// import below is what actually pulls in the module tree that needs mocking —
// keeping it after the mocks here matches evaluation order and avoids the
// temptation to "clean up" by moving it to the top.
import HomeClient from "@/app/_components/HomeClient";

describe("HomeClient — LeftNavRail auth gating", () => {
  beforeEach(() => {
    mockUseIsAuthenticated.mockReset();
  });

  it("hides the left nav rail when the user is not authenticated", () => {
    mockUseIsAuthenticated.mockReturnValue(false);

    render(<HomeClient />);

    expect(
      screen.queryByRole("navigation", { name: "Navigation entre les pages" }),
    ).not.toBeInTheDocument();
  });

  it("shows the left nav rail once the user is authenticated", () => {
    mockUseIsAuthenticated.mockReturnValue(true);

    render(<HomeClient />);

    expect(
      screen.getByRole("navigation", { name: "Navigation entre les pages" }),
    ).toBeInTheDocument();
  });
});
