"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CVData } from "@/lib/api/types";
import CVDetailSection from "./CVDetailSection";
import HomeMapSection from "./HomeMapSection";
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
  // Bumped on upload, zone save, marking a match seen, and a manual ROME
  // reanalysis — anything that can change a CV's unseen_count badge or its
  // rome_reanalysis_available flag in the library.
  const [libraryRefreshTrigger, setLibraryRefreshTrigger] = useState(0);
  const [libraryAccessible, setLibraryAccessible] = useState(false);
  const [optimisticUpload, setOptimisticUpload]   = useState<OptimisticUpload | null>(null);
  const [selectedCvId, setSelectedCvId]           = useState<string | null>(null);
  const [cvList, setCvList]                       = useState<CVData[]>([]);
  const [zoneVersion, setZoneVersion]             = useState(0);
  const detailRef                                  = useRef<HTMLElement>(null);
  const uploadSectionRef                           = useRef<UploadSectionHandle>(null);

  // Holds the cv_id from POST /cv/upload so we can set it on the optimistic
  // entry even if the POST response arrives before the animation ends.
  const uploadedCvIdRef = useRef<string | null>(null);

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

  // A manual ROME reanalysis just completed — refetch the CV list so
  // rome_reanalysis_available flips back to false once cvs.rome_analyzed_at updates.
  const handleRomeReanalyzed = useCallback(() => {
    setLibraryRefreshTrigger((n) => n + 1);
  }, []);

  return (
    // Below md the swipe/scroll navigation between the full-screen sections
    // is disabled (overflow-hidden): moving around goes through the pinned
    // mobile menu (layout.tsx), which scrolls this container programmatically
    // — scrollIntoView still scrolls an overflow-hidden box.
    <main
      className="h-dvh overflow-hidden md:snap-y md:snap-mandatory md:overflow-y-scroll"
    >
      <HomeMapSection
        uploadProps={{
          onUploadComplete: handleUploadComplete,
          onAnimationComplete: handleAnimationComplete,
          libraryAccessible,
          onScrollToLibrary: handleCloseDetail,
        }}
        uploadSectionRef={uploadSectionRef}
        onZoneSaved={handleZoneSaved}
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
          onRomeReanalyzed={handleRomeReanalyzed}
        />
      )}
    </main>
  );
}
