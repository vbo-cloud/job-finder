"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CVData } from "@/lib/api/types";
import CVDetailSection from "./CVDetailSection";
import HomeMapSection from "./HomeMapSection";
import LibrarySection from "./LibrarySection";

interface OptimisticUpload {
  thumbnailUrl: string;
  cvId: string | null;
}

export default function HomeClient() {
  // Bumped on upload, zone save, and marking a match seen — anything that can
  // change a CV's unseen_count badge in the library.
  const [libraryRefreshTrigger, setLibraryRefreshTrigger] = useState(0);
  const [libraryAccessible, setLibraryAccessible] = useState(false);
  const [optimisticUpload, setOptimisticUpload]   = useState<OptimisticUpload | null>(null);
  const [selectedCvId, setSelectedCvId]           = useState<string | null>(null);
  const [cvList, setCvList]                       = useState<CVData[]>([]);
  const [zoneVersion, setZoneVersion]             = useState(0);
  const detailRef                                  = useRef<HTMLElement>(null);

  // Holds the cv_id from POST /cv/upload so we can set it on the optimistic
  // entry even if the POST response arrives before the animation ends.
  const uploadedCvIdRef = useRef<string | null>(null);

  // Keep CVDetailSection pre-mounted: auto-select cvList[0] when no valid
  // selection exists, clear to null only when the library is empty.
  useEffect(() => {
    if (cvList.length === 0) {
      setSelectedCvId(null);
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
      detailRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, []);

  // Back action from CVDetailSection: scroll to library without unmounting the section.
  const handleCloseDetail = useCallback(() => {
    document.getElementById("library")?.scrollIntoView({ behavior: "smooth" });
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

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <HomeMapSection
        uploadProps={{
          onUploadComplete: handleUploadComplete,
          onAnimationComplete: handleAnimationComplete,
          libraryAccessible,
        }}
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
  );
}
