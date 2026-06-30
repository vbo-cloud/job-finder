"use client";

import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { CVData } from "@/lib/api/types";

import CVCard from "./CVCard";
import CVCardPlaceholder from "./CVCardPlaceholder";
import CVCardSkeleton from "./CVCardSkeleton";

const POLL_INTERVAL_MS = 3000;
const MAX_CVS = 10;

interface Props {
  /** Increment to trigger a manual re-fetch (e.g. right after an upload). */
  refreshTrigger?: number;
  /** Fires whenever the library becomes accessible (authenticated + ≥1 CV) or not. */
  onAccessibilityChange?: (accessible: boolean) => void;
}

export default function LibrarySection({ refreshTrigger = 0, onAccessibilityChange }: Props) {
  const isAuthenticated        = useIsAuthenticated();
  const [cvs, setCvs]          = useState<CVData[]>([]);
  const [loading, setLoading]  = useState(true);
  const [error, setError]      = useState(false);

  const handleCvDeleted = useCallback((id: string) => {
    setCvs((prev) => prev.filter((cv) => cv.id !== id));
  }, []);

  const fetchCvs = useCallback(async (): Promise<void> => {
    try {
      const { data } = await apiClient.get<CVData[]>("/cv/");
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

  const accessible = isAuthenticated && cvs.length > 0;

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

  return (
    <section
      id="library"
      className={cn(
        "relative h-dvh bg-page flex flex-col items-center justify-center px-6 py-8",
        accessible ? "snap-start" : "hidden",
      )}
    >
      <p className="absolute top-8 text-[9px] tracking-widest text-label">BIBLIOTHÈQUE</p>

      {/* Skeleton pendant le chargement initial (avant qu'un premier CV soit connu) */}
      {loading && cvs.length === 0 && (
        <div className="grid grid-cols-5 gap-x-5 gap-y-2">
          {Array.from({ length: 10 }).map((_, i) => <CVCardSkeleton key={i} />)}
        </div>
      )}

      {/* Grille CVs + emplacements libres */}
      {cvs.length > 0 && (
        <div className="grid grid-cols-5 gap-x-5 gap-y-2">
          {cvs.slice(0, MAX_CVS).map((cv) => (
            <CVCard key={cv.id} cv={cv} onDeleted={handleCvDeleted} />
          ))}
          {Array.from({ length: MAX_CVS - Math.min(cvs.length, MAX_CVS) }).map((_, i) => (
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
