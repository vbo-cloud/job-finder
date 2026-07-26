import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";

const push = jest.fn();
let pathname = "/";
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => pathname,
}));

const confirmNavigation = jest.fn().mockResolvedValue(true);
jest.mock("@/lib/navigation/UnsavedChangesContext", () => ({
  useUnsavedChanges: () => ({ confirmNavigation }),
}));

import MobileNavMenu from "@/app/_components/MobileNavMenu";

// jsdom has no scrollIntoView — each fixture section carries its own mock.
function addSection(id: string): { el: HTMLElement; scrollIntoView: jest.Mock } {
  const el = document.createElement("section");
  el.id = id;
  const scrollIntoView = jest.fn();
  el.scrollIntoView = scrollIntoView;
  document.body.appendChild(el);
  return { el, scrollIntoView };
}

function openMenu() {
  fireEvent.click(screen.getByRole("button", { name: "Ouvrir le menu de navigation" }));
}

describe("MobileNavMenu", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    pathname = "/";
    // Sections appended by previous tests must not leak availability.
    document.querySelectorAll("section").forEach((s) => s.remove());
  });

  it("opens the panel with the section entries and the profile link", () => {
    addSection("home");
    render(<MobileNavMenu />);
    openMenu();

    expect(screen.getByRole("navigation", { name: "Navigation principale" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accueil" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Mon profil" })).toHaveAttribute("href", "/profile");
  });

  it("scrolls to an available section and closes the panel", () => {
    addSection("home");
    const library = addSection("library");
    render(<MobileNavMenu />);
    openMenu();

    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));

    // Instant jump on purpose — smooth scrolling stalls on the
    // overflow-hidden mobile container (see MobileNavMenu.goToSection).
    expect(library.scrollIntoView).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("disables entries whose section is absent on the home page", () => {
    addSection("home");
    render(<MobileNavMenu />);
    openMenu();

    // No CV selected: the correspondances section is not mounted.
    expect(screen.getByRole("button", { name: "Correspondances" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Accueil" })).toBeEnabled();
  });

  it("navigates to the home page when a section entry is used from another route", async () => {
    pathname = "/profile";
    render(<MobileNavMenu />);
    openMenu();

    const accueil = screen.getByRole("button", { name: "Accueil" });
    expect(accueil).toBeEnabled(); // away from home, entries always lead somewhere
    fireEvent.click(accueil);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("does not navigate when the unsaved-changes guard is declined", async () => {
    pathname = "/profile";
    confirmNavigation.mockResolvedValueOnce(false);
    render(<MobileNavMenu />);
    openMenu();

    fireEvent.click(screen.getByRole("button", { name: "Accueil" }));
    await waitFor(() => expect(confirmNavigation).toHaveBeenCalled());

    expect(push).not.toHaveBeenCalled();
  });

  it("guards the profile/feedback links through the same confirmation", async () => {
    confirmNavigation.mockResolvedValueOnce(false);
    render(<MobileNavMenu />);
    openMenu();

    fireEvent.click(screen.getByRole("link", { name: "Mon profil" }));
    await waitFor(() => expect(confirmNavigation).toHaveBeenCalled());

    expect(push).not.toHaveBeenCalled();
    // The panel stays open — navigation was declined, "Mon profil" is still there.
    expect(screen.getByRole("link", { name: "Mon profil" })).toBeInTheDocument();
  });
});
