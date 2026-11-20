import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";

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

// enterMap/exitMap are asserted directly instead of exercising the real
// wheel-driven CV/map fade — that transition timing belongs to
// HomeMapSection's own tests, not HomeClient's orchestration around it.
const enterMapMock = jest.fn();
const exitMapMock = jest.fn();
// Captured so tests can simulate the mode HomeMapSection would report at the
// end of its own transition (see TRANSITION_MS in HomeMapSection.tsx), without
// needing that real timer here.
let reportMode: ((mode: string) => void) | null = null;

jest.mock("@/app/_components/HomeMapSection", () => ({
  __esModule: true,
  default: React.forwardRef(function HomeMapSectionStub(
    props: { onModeChange?: (mode: string) => void },
    ref: React.Ref<{ enterMap: () => void; exitMap: () => void }>,
  ) {
    reportMode = props.onModeChange ?? null;
    React.useImperativeHandle(ref, () => ({ enterMap: enterMapMock, exitMap: exitMapMock }));
    return <section id="home" data-testid="home-section-stub" />;
  }),
}));

// Reports itself accessible on mount, like the real component once its
// initial fetch resolves — otherwise LeftNavRail's Bibliothèque icon stays
// disabled and clicks on it are inert, same as a real disabled button. Also
// reports one CV so HomeClient auto-selects it (see its cvList effect),
// mounting CVDetailSection and enabling the Offres icon below.
jest.mock("@/app/_components/LibrarySection", () => ({
  __esModule: true,
  default: function LibrarySectionStub(props: {
    onAccessibilityChange?: (accessible: boolean) => void;
    onCvsChange?: (cvs: unknown[]) => void;
  }) {
    // Empty deps array — a fresh props object every render (a new
    // [{ id: "cv-1" }] literal in particular) would re-fire this on every
    // render and loop forever via onCvsChange → setCvList → re-render → new
    // props if props itself were a dependency. The refs below only exist so
    // the effect still reads the latest callbacks without capturing a stale
    // closure over the initial props (same pattern the skill prescribes for
    // "a value that changes too often — use a ref rather than dropping it
    // from deps", applied here to keep deps empty on purpose).
    const onAccessibilityChangeRef = React.useRef(props.onAccessibilityChange);
    onAccessibilityChangeRef.current = props.onAccessibilityChange;
    const onCvsChangeRef = React.useRef(props.onCvsChange);
    onCvsChangeRef.current = props.onCvsChange;
    React.useEffect(() => {
      onAccessibilityChangeRef.current?.(true);
      onCvsChangeRef.current?.([{ id: "cv-1" }]);
    }, []);
    return <section id="library" data-testid="library-section-stub" />;
  },
}));

jest.mock("@/app/_components/CVDetailSection", () => ({
  __esModule: true,
  default: React.forwardRef(function CVDetailSectionStub(_props: unknown, ref: React.Ref<HTMLElement>) {
    return <section id="cv-detail" ref={ref} data-testid="cv-detail-section-stub" />;
  }),
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

// jsdom has no IntersectionObserver — this fake lets tests drive
// HomeClient's activeSection the same way real scroll would, by invoking the
// callback it registered with a fabricated entry list.
let ioCallback: IntersectionObserverCallback | null = null;

class FakeIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [];
  constructor(callback: IntersectionObserverCallback) {
    ioCallback = callback;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

function fireIntersection(target: Element) {
  act(() => {
    // The real callback ignores its 2nd (observer) argument — passed as {}
    // rather than another FakeIntersectionObserver instance, whose
    // constructor would otherwise overwrite the captured `ioCallback` with
    // a throwaway no-op before this call even runs.
    ioCallback?.(
      [{ target, isIntersecting: true, intersectionRatio: 1 } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
  });
}

global.IntersectionObserver = FakeIntersectionObserver as unknown as typeof IntersectionObserver;

describe("HomeClient — LeftNavRail scroll orchestration", () => {
  beforeEach(() => {
    mockUseIsAuthenticated.mockReturnValue(true);
    enterMapMock.mockReset();
    exitMapMock.mockReset();
    ioCallback = null;
    reportMode = null;
  });

  it("defers entering the map until the scroll has actually landed on home", () => {
    render(<HomeClient />);
    const home = screen.getByTestId("home-section-stub");
    const library = screen.getByTestId("library-section-stub");
    home.scrollIntoView = jest.fn();
    library.scrollIntoView = jest.fn();

    // Scrolled away to the library — the rail highlights it, not home.
    fireIntersection(library);

    fireEvent.click(screen.getByRole("button", { name: "Carte — zone de recherche" }));

    // The section scroll starts right away, but the map fade must wait —
    // otherwise the user never sees Accueil (the CV layer) pass by.
    expect(home.scrollIntoView).toHaveBeenCalledTimes(1);
    expect(enterMapMock).not.toHaveBeenCalled();

    // The scroll lands: home is now the most visible section.
    fireIntersection(home);

    expect(enterMapMock).toHaveBeenCalledTimes(1);
  });

  it("enters the map immediately when already on home", () => {
    render(<HomeClient />);
    const home = screen.getByTestId("home-section-stub");
    home.scrollIntoView = jest.fn();

    fireEvent.click(screen.getByRole("button", { name: "Carte — zone de recherche" }));

    expect(enterMapMock).toHaveBeenCalledTimes(1);
    expect(home.scrollIntoView).not.toHaveBeenCalled();
  });

  it("defers scrolling to the library until the map's reverse fade has settled", () => {
    render(<HomeClient />);
    const library = screen.getByTestId("library-section-stub");
    library.scrollIntoView = jest.fn();

    // Simulate the map already being focused (as HomeMapSection would report
    // through onModeChange after the wheel-driven enterMap transition).
    act(() => reportMode?.("map"));

    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));

    // exitMap fires immediately, but the library scroll must wait for the
    // reverse fade to land back on "cv" — otherwise the map silently
    // backgrounds itself instead of visibly handing back to Accueil.
    expect(exitMapMock).toHaveBeenCalledTimes(1);
    expect(library.scrollIntoView).not.toHaveBeenCalled();

    // The reverse fade settles.
    act(() => reportMode?.("cv"));

    expect(library.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("scrolls to the library immediately when the map isn't focused", () => {
    render(<HomeClient />);
    const library = screen.getByTestId("library-section-stub");
    library.scrollIntoView = jest.fn();

    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));

    expect(exitMapMock).not.toHaveBeenCalled();
    expect(library.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("defers scrolling to the offers section until the map's reverse fade has settled", () => {
    render(<HomeClient />);
    const detail = screen.getByTestId("cv-detail-section-stub");
    detail.scrollIntoView = jest.fn();

    act(() => reportMode?.("map"));

    fireEvent.click(screen.getByRole("button", { name: "Offres" }));

    expect(exitMapMock).toHaveBeenCalledTimes(1);
    expect(detail.scrollIntoView).not.toHaveBeenCalled();

    act(() => reportMode?.("cv"));

    expect(detail.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("never enters the map if a different nav target is chosen before the scroll lands on home", () => {
    render(<HomeClient />);
    const home = screen.getByTestId("home-section-stub");
    const library = screen.getByTestId("library-section-stub");
    home.scrollIntoView = jest.fn();
    library.scrollIntoView = jest.fn();

    // Scrolled away to the library, then Carte is clicked — same setup as
    // the "defers entering the map" case above.
    fireIntersection(library);
    fireEvent.click(screen.getByRole("button", { name: "Carte — zone de recherche" }));
    expect(home.scrollIntoView).toHaveBeenCalledTimes(1);

    // Before home is ever reported as active, the user picks Bibliothèque
    // instead — this must cancel the pending enterMap, not just redirect
    // the scroll.
    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));
    expect(library.scrollIntoView).toHaveBeenCalledTimes(1);

    // Home eventually reports itself active anyway (e.g. the superseded
    // scroll settles, or the user later scrolls back through it manually) —
    // the map must not spring open at that point.
    fireIntersection(home);
    expect(enterMapMock).not.toHaveBeenCalled();
  });

  it("Accueil cancels a pending enterMap from a previous Carte click", () => {
    render(<HomeClient />);
    const home = screen.getByTestId("home-section-stub");
    home.scrollIntoView = jest.fn();

    fireIntersection(screen.getByTestId("library-section-stub"));
    fireEvent.click(screen.getByRole("button", { name: "Carte — zone de recherche" }));
    expect(home.scrollIntoView).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Accueil — import de CV" }));
    expect(home.scrollIntoView).toHaveBeenCalledTimes(2);

    // A later (stale) "home is active" report must not trigger enterMap —
    // the Accueil click already cancelled that intent.
    fireIntersection(home);
    expect(enterMapMock).not.toHaveBeenCalled();
  });

  it("Accueil cancels a pending post-exit scroll from a previous Bibliothèque click", () => {
    render(<HomeClient />);
    const home = screen.getByTestId("home-section-stub");
    const library = screen.getByTestId("library-section-stub");
    home.scrollIntoView = jest.fn();
    library.scrollIntoView = jest.fn();

    act(() => reportMode?.("map"));
    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));
    expect(exitMapMock).toHaveBeenCalledTimes(1);

    // Mode hasn't settled back to "cv" yet — Accueil is clicked instead,
    // which must cancel the pending scroll to the library.
    fireEvent.click(screen.getByRole("button", { name: "Accueil — import de CV" }));

    act(() => reportMode?.("cv"));
    expect(library.scrollIntoView).not.toHaveBeenCalled();
  });

  it("Carte cancels a pending post-exit scroll from a previous Bibliothèque click", () => {
    render(<HomeClient />);
    const library = screen.getByTestId("library-section-stub");
    library.scrollIntoView = jest.fn();

    act(() => reportMode?.("map"));
    fireEvent.click(screen.getByRole("button", { name: "Bibliothèque" }));
    expect(exitMapMock).toHaveBeenCalledTimes(1);

    // Mode hasn't settled back to "cv" yet — Carte is clicked instead
    // (already on "home", so it re-enters the map immediately) — this must
    // cancel the pending scroll to the library too.
    fireEvent.click(screen.getByRole("button", { name: "Carte — zone de recherche" }));
    expect(enterMapMock).toHaveBeenCalledTimes(1);

    act(() => reportMode?.("cv"));
    expect(library.scrollIntoView).not.toHaveBeenCalled();
  });
});
