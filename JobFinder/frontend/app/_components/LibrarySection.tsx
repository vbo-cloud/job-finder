"use client";

import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { CVData } from "@/lib/api/types";

import CVCard from "./CVCard";
import CVCardOptimistic from "./CVCardOptimistic";
import CVCardPlaceholder from "./CVCardPlaceholder";
import CVCardSkeleton from "./CVCardSkeleton";

const POLL_INTERVAL_MS = 3000;
const MAX_CVS = 10;

interface OptimisticUpload {
  thumbnailUrl: string;
  cvId: string | null;
}

interface Props {
  /** Increment to trigger a manual re-fetch (e.g. right after an upload). */
  refreshTrigger?: number;
  /** Fires whenever the library becomes accessible (authenticated + ≥1 CV) or not. */
  onAccessibilityChange?: (accessible: boolean) => void;
  /** Local thumbnail to display immediately after the upload animation. */
  optimisticUpload?: OptimisticUpload | null;
  /** Called once the real CV is confirmed in the list so the parent can revoke the objectURL. */
  onOptimisticConsumed?: () => void;
}

export default function LibrarySection({
  refreshTrigger = 0,
  onAccessibilityChange,
  optimisticUpload,
  onOptimisticConsumed,
}: Props) {
  const isAuthenticated        = useIsAuthenticated();
  const [cvs, setCvs]          = useState<CVData[]>([]);
  const [loading, setLoading]  = useState(true);
  const [error, setError]      = useState(false);

  const handleCvDeleted = useCallback((id: string) => {
    setCvs((prev) => prev.filter((cv) => cv.id !== id));
  }, []);

  const fetchCvs = useCallback(async (): Promise<void> => {
    const tryFetch = () => apiClient.get<CVData[]>("/cv/");
    try {
      // Retry once after a short delay to absorb transient MSAL token
      // acquisition failures that can occur on the first page load.
      const { data } = await tryFetch().catch(async () => {
        await new Promise<void>((res) => setTimeout(res, 1500));
        return tryFetch();
      });
      setCvs(data);
      setError(false);
    } catch (err) {
      console.error("[LibrarySection] fetch failed", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    setLoading(true);
    void fetchCvs();
  }, [fetchCvs, isAuthenticated, refreshTrigger]);

  // Consume the optimistic entry once the real CV (matched by id) is in the list.
  useEffect(() => {
    if (!optimisticUpload?.cvId) return;
    if (cvs.some((cv) => cv.id === optimisticUpload.cvId)) {
      onOptimisticConsumed?.();
    }
  }, [cvs, optimisticUpload, onOptimisticConsumed]);

  // Show the optimistic card while the cv_id is unknown (POST still in flight)
  // OR while the real CV hasn't appeared in the fetched list yet.
  const showOptimistic =
    !!optimisticUpload &&
    (optimisticUpload.cvId === null ||
      !cvs.some((cv) => cv.id === optimisticUpload.cvId));

  // Accessible as soon as we know at least one CV exists — stays accessible during
  // re-fetches so the section doesn't flicker hidden on every upload.
  const accessible = isAuthenticated && (cvs.length > 0 || showOptimistic);

  useEffect(() => {
    onAccessibilityChange?.(accessible);
  }, [accessible, onAccessibilityChange]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const hasPending = cvs.some(
      (cv) => cv.status === "pending" || cv.status === "processing",
    );
    if (!hasPending) return;

    const id = setInterval(() => void fetchCvs(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [cvs, fetchCvs, isAuthenticated]);

  // When showing the optimistic card, it occupies the first slot; real CVs fill the rest.
  const optimisticCount  = showOptimistic ? 1 : 0;
  const realCvs          = showOptimistic ? cvs.slice(0, MAX_CVS - 1) : cvs.slice(0, MAX_CVS);
  const placeholderCount = Math.max(0, MAX_CVS - optimisticCount - realCvs.length);
  const showGrid         = showOptimistic || cvs.length > 0;

  return (
    <section
      id="library"
      className={cn(
        "relative h-dvh bg-page flex flex-col items-center justify-center px-6 py-8",
        accessible ? "snap-start" : "hidden",
      )}
    >
      <p className="absolute top-8 text-[9px] tracking-widest text-label">BIBLIOTHÈQUE</p>

      {/* Skeleton only on initial load, before any CV (real or optimistic) is known */}
      {loading && !showGrid && (
        <div className="grid grid-cols-5 gap-x-5 gap-y-2">
          {Array.from({ length: 10 }).map((_, i) => <CVCardSkeleton key={i} />)}
        </div>
      )}

      {/* Grid: optimistic slot + real CVs + empty placeholders */}
      {showGrid && (
        <div className="grid grid-cols-5 gap-x-5 gap-y-2">
          {showOptimistic && (
            <CVCardOptimistic thumbnailUrl={optimisticUpload!.thumbnailUrl} />
          )}
          {realCvs.map((cv) => (
            <CVCard key={cv.id} cv={cv} onDeleted={handleCvDeleted} />
          ))}
          {Array.from({ length: placeholderCount }).map((_, i) => (
            <CVCardPlaceholder key={`placeholder-${i}`} />
          ))}
        </div>
      )}

      {isAuthenticated && error && (
        <p className="mt-4 text-xs text-destructive">Impossible de charger les CVs.</p>
      )}
    </section>
  );
}
