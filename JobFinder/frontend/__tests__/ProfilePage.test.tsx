import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: { get: jest.fn(), put: jest.fn() },
}));

jest.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => true,
  // getActiveAccount is required here — ProfilePage now reads it (falling
  // back to accounts[0]) instead of accounts[0] directly.
  useMsal: jest.fn(() => ({
    instance: {
      loginRedirect: jest.fn(),
      logoutRedirect: jest.fn(),
      getActiveAccount: jest.fn().mockReturnValue({ name: "Test User" }),
    },
    accounts: [{ name: "Test User" }],
  })),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: { setPersonProperties: jest.fn(), capture: jest.fn() },
}));

jest.mock("@/lib/auth/msalConfig", () => ({
  loginRequest: { scopes: [] },
}));

const unsavedChanges = {
  setHasUnsavedChanges: jest.fn(),
  registerSaveHandler: jest.fn(),
  confirmNavigation: jest.fn().mockResolvedValue(true),
};
jest.mock("@/lib/navigation/UnsavedChangesContext", () => ({
  useUnsavedChanges: () => unsavedChanges,
}));

import { useMsal } from "@azure/msal-react";

import ProfilePage from "@/app/profile/page";
import apiClient from "@/lib/api/client";

async function renderLoaded() {
  render(<ProfilePage />);
  // Flush the initial GET /profile promise chain (then + finally).
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("ProfilePage — notification_days autosave", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        experience_level: null,
        notification_days: [],
        candidate_description: "",
        analysis_credits_remaining: 5,
        is_admin: false,
      },
    });
    (apiClient.put as jest.Mock).mockResolvedValue({});
  });

  it("debounces a notification day toggle into a single PUT of notification_days only", async () => {
    jest.useFakeTimers();
    await renderLoaded();

    fireEvent.click(screen.getByRole("button", { name: "Lun" }));
    expect(apiClient.put).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(800);
    });

    expect(apiClient.put).toHaveBeenCalledTimes(1);
    expect(apiClient.put).toHaveBeenCalledWith("/profile", { notification_days: [1] });

    jest.useRealTimers();
  });

  it("collapses several toggles within the debounce window into a single PUT", async () => {
    jest.useFakeTimers();
    await renderLoaded();

    fireEvent.click(screen.getByRole("button", { name: "Lun" }));
    await act(async () => {
      jest.advanceTimersByTime(400);
    });
    fireEvent.click(screen.getByRole("button", { name: "Mar" }));

    await act(async () => {
      jest.advanceTimersByTime(800);
    });

    expect(apiClient.put).toHaveBeenCalledTimes(1);
    expect(apiClient.put).toHaveBeenCalledWith("/profile", { notification_days: [1, 2] });

    jest.useRealTimers();
  });

  it("does not include notification_days when saving the experience/description block", async () => {
    await renderLoaded();

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiClient.put).toHaveBeenCalledTimes(1);
    const [, body] = (apiClient.put as jest.Mock).mock.calls[0];
    expect(body).not.toHaveProperty("notification_days");
    expect(body).toEqual({ experience_level: null, candidate_description: null });
  });

  it("does not mark the page dirty (unsaved-changes guard) from a notification toggle alone", async () => {
    await renderLoaded();
    unsavedChanges.setHasUnsavedChanges.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Lun" }));

    expect(unsavedChanges.setHasUnsavedChanges).not.toHaveBeenCalledWith(true);
  });
});

describe("ProfilePage — displayed account with multiple MSAL cache entries", () => {
  const defaultUseMsal = (useMsal as jest.Mock).getMockImplementation();

  beforeEach(() => {
    jest.clearAllMocks();
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        experience_level: null,
        notification_days: [],
        candidate_description: "",
        analysis_credits_remaining: 5,
        is_admin: false,
      },
    });
  });

  // Restore the module's default useMsal mock so this override never leaks
  // into a test in another describe block that runs after this one.
  afterEach(() => {
    (useMsal as jest.Mock).mockImplementation(defaultUseMsal);
  });

  it("shows the active account's name, not accounts[0], when two accounts are cached", async () => {
    (useMsal as jest.Mock).mockReturnValue({
      instance: {
        loginRedirect: jest.fn(),
        logoutRedirect: jest.fn(),
        getActiveAccount: jest.fn().mockReturnValue({ name: "Second User" }),
      },
      accounts: [{ name: "First User" }, { name: "Second User" }],
    });

    await renderLoaded();

    expect(screen.getByRole("heading", { name: "Second User" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "First User" })).not.toBeInTheDocument();
  });
});
