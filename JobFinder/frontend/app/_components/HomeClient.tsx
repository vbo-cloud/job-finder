"use client";

import { useIsAuthenticated } from "@azure/msal-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { CVData } from "@/lib/api/types";
import CVDetailSection from "./CVDetailSection";
import HomeMapSection, { type HomeMapSectionHandle, type Mode } from "./HomeMapSection";
import LeftNavRail, { type ActiveSection } from "./LeftNavRail";
import LibrarySection from "./LibrarySection";
import type { UploadSectionHandle } from "./UploadSection";

interface OptimisticUpload {
  thumbnailUrl: string;
  cvId: string | null;
}

// Smooth scrolling stalls midway on the overflow-hidden mobile container
// (Chrome drops the animation when nested scrollers are involved) — below md
// the sections jump instantly, which also matches the menu-driven "page"
// navigation; the desktop snap container keeps its animation. The
// typeof guard covers jsdom, where matchMedia does not exist.
const sectionScrollBehavior = (): ScrollBehavior =>
  typeof window.matchMedia === "function" && window.matchMedia("(min-width: 768px)").matches
    ? "smooth"
    : "auto";

export default function HomeClient() {
  // Bumped on upload, zone save, and marking a match seen — anything that
  // can change a CV's unseen_count badge in the library.
  const [libraryRefreshTrigger, setLibraryRefreshTrigger] = useState(0);
  const [libraryAccessible, setLibraryAccessible] = useState(false);
  const [optimisticUpload, setOptimisticUpload]   = useState<OptimisticUpload | null>(null);
  const [selectedCvId, setSelectedCvId]           = useState<string | null>(null);
  const [cvList, setCvList]                       = useState<CVData[]>([]);
  const [zoneVersion, setZoneVersion]             = useState(0);
  const [mode, setMode]                           = useState<Mode>("cv");
  const [activeSection, setActiveSection]         = useState<ActiveSection>("home");
  const detailRef                                  = useRef<HTMLElement>(null);
  const uploadSectionRef                           = useRef<UploadSectionHandle>(null);
  const homeMapSectionRef                          = useRef<HomeMapSectionHandle>(null);
  const mainRef                                    = useRef<HTMLElement>(null);
  const isAuthenticated                            = useIsAuthenticated();

  // Holds the cv_id from POST /cv/upload so we can set it on the optimistic
  // entry even if the POST response arrives before the animation ends.
  const uploadedCvIdRef = useRef<string | null>(null);

  // Set by handleGoMap when the rail is clicked from library/cv-detail: entering
  // map mode is deferred until the scroll has actually landed on "home", so the
  // user sees the CV layer (and its fade into the map) instead of the two
  // firing in the same tick and skipping the visual pass through Accueil.
  const pendingEnterMapRef = useRef(false);
  // Set by handleGoLibrary/handleGoOffers when clicked while the map is
  // focused: the section scroll is deferred until the reverse (map → cv)
  // fade has settled, for the same reason — otherwise the map is silently
  // backgrounded instead of visibly handing back to Accueil.
  const pendingExitTargetRef = useRef<"library" | "cv-detail" | null>(null);

  // Keep CVDetailSection pre-mounted: auto-select cvList[0] when no valid
  // selection exists, clear to null only when the library is empty.
  useEffect(() => {
    if (cvList.length === 0) {
      if (selectedCvId) {
        // Last CV just deleted: the library section hides itself and the
        // detail section unmounts — send the user back to the home section
        // rather than leaving the scroll stranded on a vanished section.
        setSelectedCvId(null);
        document.getElementById("home")?.scrollIntoView({ behavior: sectionScrollBehavior() });
      }
      return;
    }
    if (selectedCvId && cvList.some((cv) => cv.id === selectedCvId)) return;
    setSelectedCvId(cvList[0].id);
  }, [cvList, selectedCvId]);

  // Drives LeftNavRail's active icon from actual scroll position rather than
  // from the last click — a manual wheel/swipe between sections must still
  // move the highlight. Re-run when selectedCvId toggles cv-detail's mount.
  useEffect(() => {
    const ids: ActiveSection[] = ["home", "library", "cv-detail"];
    const sections = ids
      .map((id) => ({ id, el: document.getElementById(id) }))
      .filter((entry): entry is { id: ActiveSection; el: HTMLElement } => entry.el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const mostVisible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        const match = sections.find((section) => section.el === mostVisible?.target);
        if (match) setActiveSection(match.id);
      },
      { root: mainRef.current, threshold: 0.5 },
    );
    sections.forEach(({ el }) => observer.observe(el));
    return () => observer.disconnect();
  }, [selectedCvId]);

  // Completes handleGoMap's deferred entry once the scroll has actually
  // landed on "home" (activeSection is the same IntersectionObserver-driven
  // signal LeftNavRail's highlight relies on, so "arrived" means the same
  // thing here as it does there).
  useEffect(() => {
    if (activeSection !== "home" || !pendingEnterMapRef.current) return;
    pendingEnterMapRef.current = false;
    homeMapSectionRef.current?.enterMap();
  }, [activeSection]);

  // Completes handleGoLibrary/handleGoOffers's deferred scroll once the
  // reverse fade has settled back on "cv" (mode mirrors HomeMapSection's own
  // state via onModeChange below).
  useEffect(() => {
    if (mode !== "cv" || !pendingExitTargetRef.current) return;
    const target = pendingExitTargetRef.current;
    pendingExitTargetRef.current = null;
    const el = target === "library" ? document.getElementById("library") : detailRef.current;
    el?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, [mode]);

  const handleUploadComplete = useCallback((cvId: string) => {
    uploadedCvIdRef.current = cvId;
    setOptimisticUpload((prev) => (prev ? { ...prev, cvId } : null));
    setLibraryRefreshTrigger((n) => n + 1);
  }, []);

  const handleAnimationComplete = useCallback((thumbnailUrl: string) => {
    if (!thumbnailUrl) return;
    const cvId = uploadedCvIdRef.current;
    uploadedCvIdRef.current = null;
    setOptimisticUpload({ thumbnailUrl, cvId });
  }, []);

  const handleOptimisticConsumed = useCallback(() => {
    setOptimisticUpload((prev) => {
      if (prev?.thumbnailUrl) URL.revokeObjectURL(prev.thumbnailUrl);
      return null;
    });
  }, []);

  // Explicit card click: select a CV and scroll into the detail section.
  const handleCvSelect = useCallback((id: string) => {
    setSelectedCvId(id);
    // Defer one frame so snap-mandatory has registered the section before scrolling.
    requestAnimationFrame(() => {
      detailRef.current?.scrollIntoView({ behavior: sectionScrollBehavior() });
    });
  }, []);

  // Back action from CVDetailSection (and the library-bound hint in
  // UploadSection): scroll to library without unmounting the section.
  const handleCloseDetail = useCallback(() => {
    document.getElementById("library")?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, []);

  // "OFFRES" hint in LibrarySection: scroll down to the already-mounted
  // detail section (a CV is auto-selected as soon as the library has one).
  const handleScrollToDetail = useCallback(() => {
    detailRef.current?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, []);

  // "ACCUEIL" hint in LibrarySection: scroll to the home/upload section.
  const handleScrollToHome = useCallback(() => {
    document.getElementById("home")?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, []);

  // "Ajouter un CV" in LibrarySection: scroll to the home/upload section and
  // open its file picker right away — the picker is a native OS dialog, so
  // it can open while the scroll is still animating behind it (unlike
  // handleScrollToHome above, no scrollend/900ms wait — that delay made the
  // picker feel slow to appear here).
  const handleAddCv = useCallback(() => {
    document.getElementById("home")?.scrollIntoView({ behavior: sectionScrollBehavior() });
    uploadSectionRef.current?.openPicker();
  }, []);

  const handleZoneSaved = useCallback(() => {
    setZoneVersion((v) => v + 1);
    setLibraryRefreshTrigger((n) => n + 1);
  }, []);

  // A match was marked seen while viewing a CV's offers — the library badge
  // (unseen_count) needs a fresh GET /cv/ to reflect it.
  const handleMatchSeen = useCallback(() => {
    setLibraryRefreshTrigger((n) => n + 1);
  }, []);

  // LeftNavRail's CV/Accueil icon: unlike handleScrollToHome above (only
  // ever reached from the library, where the map is never focused), this one
  // can fire while the map layer is focused — leave it first so landing on
  // "home" always shows the CV layer, not the map. Every rail click is a
  // fresh intent that supersedes whatever a previous click was waiting on,
  // so each handler below clears both pending refs before (re)setting one.
  const handleGoHome = useCallback(() => {
    pendingEnterMapRef.current = false;
    pendingExitTargetRef.current = null;
    if (mode === "map" || mode === "to-map") homeMapSectionRef.current?.exitMap();
    document.getElementById("home")?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, [mode]);

  // LeftNavRail's Carte icon. From library/cv-detail this used to scroll to
  // "home" and call enterMap() in the same tick — the map fade started before
  // the section had even scrolled into view, so the user landed straight on
  // the map without ever seeing Accueil pass by. Now enterMap() only fires
  // once activeSection confirms "home" is actually in view (see the effect
  // above); already on "home", it fires immediately, same as before.
  const handleGoMap = useCallback(() => {
    pendingExitTargetRef.current = null;
    if (activeSection !== "home") {
      pendingEnterMapRef.current = true;
      document.getElementById("home")?.scrollIntoView({ behavior: sectionScrollBehavior() });
      return;
    }
    pendingEnterMapRef.current = false;
    homeMapSectionRef.current?.enterMap();
  }, [activeSection]);

  // LeftNavRail's Bibliothèque icon. Mirrors handleGoMap: if the map is
  // focused, exitMap() first and defer the scroll to the effect above so the
  // reverse fade is visible instead of the map silently backgrounding itself
  // while the page jumps straight to the library.
  const handleGoLibrary = useCallback(() => {
    pendingEnterMapRef.current = false;
    if (mode === "map" || mode === "to-map") {
      pendingExitTargetRef.current = "library";
      homeMapSectionRef.current?.exitMap();
      return;
    }
    pendingExitTargetRef.current = null;
    document.getElementById("library")?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, [mode]);

  // LeftNavRail's Offres icon — same reasoning as handleGoLibrary above, kept
  // separate from handleScrollToDetail (used by in-section hints that are
  // never reachable while the map is focused).
  const handleGoOffers = useCallback(() => {
    pendingEnterMapRef.current = false;
    if (mode === "map" || mode === "to-map") {
      pendingExitTargetRef.current = "cv-detail";
      homeMapSectionRef.current?.exitMap();
      return;
    }
    pendingExitTargetRef.current = null;
    detailRef.current?.scrollIntoView({ behavior: sectionScrollBehavior() });
  }, [mode]);

  return (
    <>
      {/* Guests previously got a degraded rail (icons dimmed via mapAvailable) —
          now hidden entirely, consistent with the rest of the guest experience. */}
      {isAuthenticated && (
        <LeftNavRail
          activeSection={activeSection}
          mapActive={mode === "map" || mode === "to-map"}
          mapAvailable
          libraryAvailable={libraryAccessible}
          offersAvailable={!!selectedCvId}
          onGoHome={handleGoHome}
          onGoMap={handleGoMap}
          onGoLibrary={handleGoLibrary}
          onGoOffers={handleGoOffers}
        />
      )}
      {/* Below md the swipe/scroll navigation between the full-screen sections
          is disabled (overflow-hidden): moving around goes through the pinned
          mobile menu (layout.tsx), which scrolls this container programmatically
          — scrollIntoView still scrolls an overflow-hidden box. */}
      <main
        ref={mainRef}
        className="h-dvh overflow-hidden md:snap-y md:snap-mandatory md:overflow-y-scroll"
      >
        <HomeMapSection
          ref={homeMapSectionRef}
          uploadProps={{
            onUploadComplete: handleUploadComplete,
            onAnimationComplete: handleAnimationComplete,
            libraryAccessible,
            onScrollToLibrary: handleCloseDetail,
          }}
          uploadSectionRef={uploadSectionRef}
          onZoneSaved={handleZoneSaved}
          onModeChange={setMode}
        />
        <LibrarySection
          refreshTrigger={libraryRefreshTrigger}
          onAccessibilityChange={setLibraryAccessible}
          optimisticUpload={optimisticUpload}
          onOptimisticConsumed={handleOptimisticConsumed}
          onCvSelect={handleCvSelect}
          onCvsChange={setCvList}
          selectedCvId={selectedCvId}
          onScrollToHome={handleScrollToHome}
          onScrollToOffers={handleScrollToDetail}
          onAddCv={handleAddCv}
        />
        {selectedCvId && (
          <CVDetailSection
            ref={detailRef}
            cvs={cvList}
            selectedCvId={selectedCvId}
            onCvChange={setSelectedCvId} // arrow nav: already on section, no scroll needed
            onClose={handleCloseDetail}
            zoneVersion={zoneVersion}
            onMatchSeen={handleMatchSeen}
          />
        )}
      </main>
    </>
  );
}
