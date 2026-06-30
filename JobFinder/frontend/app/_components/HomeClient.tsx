"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { CVData } from "@/lib/api/types";
import CVDetailSection from "./CVDetailSection";
import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

interface OptimisticUpload {
  thumbnailUrl: string;
  cvId: string | null;
}

export default function HomeClient() {
  const [uploadCount, setUploadCount]             = useState(0);
  const [libraryAccessible, setLibraryAccessible] = useState(false);
  const [optimisticUpload, setOptimisticUpload]   = useState<OptimisticUpload | null>(null);
  const [selectedCvId, setSelectedCvId]           = useState<string | null>(null);
  const [cvList, setCvList]                       = useState<CVData[]>([]);
  const detailRef                                  = useRef<HTMLElement>(null);

  // Holds the cv_id from POST /cv/upload so we can set it on the optimistic
  // entry even if the POST response arrives before the animation ends.
  const uploadedCvIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selectedCvId || !detailRef.current) return;
    const el = detailRef.current;
    // Defer one frame so the snap container registers the newly-mounted snap
    // target before we scroll — without this, snap-mandatory can snap back.
    requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: "smooth" });
    });
  }, [selectedCvId]);

  // Fires when the upload HTTP response comes back (with the new cv_id).
  const handleUploadComplete = useCallback((cvId: string) => {
    uploadedCvIdRef.current = cvId;
    setOptimisticUpload((prev) => (prev ? { ...prev, cvId } : null));
    setUploadCount((n) => n + 1);
  }, []);

  // Fires when the descend animation finishes — thumbnail objectURL still alive.
  const handleAnimationComplete = useCallback((thumbnailUrl: string) => {
    if (!thumbnailUrl) return;
    // If the POST already responded, attach its cv_id immediately so the
    // LibrarySection effect can resolve the optimistic in the first render.
    const cvId = uploadedCvIdRef.current;
    uploadedCvIdRef.current = null;
    setOptimisticUpload({ thumbnailUrl, cvId });
  }, []);

  // Called by LibrarySection once the real CV is confirmed in the list.
  const handleOptimisticConsumed = useCallback(() => {
    setOptimisticUpload((prev) => {
      if (prev?.thumbnailUrl) URL.revokeObjectURL(prev.thumbnailUrl);
      return null;
    });
  }, []);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection
        onUploadComplete={handleUploadComplete}
        onAnimationComplete={handleAnimationComplete}
        libraryAccessible={libraryAccessible}
      />
      <LibrarySection
        refreshTrigger={uploadCount}
        onAccessibilityChange={setLibraryAccessible}
        optimisticUpload={optimisticUpload}
        onOptimisticConsumed={handleOptimisticConsumed}
        onCvSelect={setSelectedCvId}
        onCvsChange={setCvList}
      />
      {selectedCvId && (
        <CVDetailSection
          ref={detailRef}
          cvs={cvList}
          selectedCvId={selectedCvId}
          onCvChange={setSelectedCvId}
          onClose={() => setSelectedCvId(null)}
        />
      )}
    </main>
  );
}
