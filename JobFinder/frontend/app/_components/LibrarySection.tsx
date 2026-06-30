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

  // Only fetch when the user is authenticated; re-fetch when refreshTrigger changes.
  // setLoading(true) ensures the skeleton appears even when loading was reset to false
  // by a prior unauthenticated render (MSAL resolves auth after the first paint).
  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    setLoading(true);
    void fetchCvs();
  }, [fetchCvs, isAuthenticated, refreshTrigger]);

  // Accessible as soon as we know at least one CV exists — stays accessible during re-fetches
  // so the section doesn't flicker hidden on every upload.
  const accessible = isAuthenticated && cvs.length > 0;

  useEffect(() => {
    onAccessibilityChange?.(accessible);
  }, [accessible, onAccessibilityChange]);

  // Poll only while at least one CV is still being analysed
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
        "relative h-dvh bg-[#0a0a0f] flex flex-col items-center justify-center px-6 py-8",
        accessible ? "snap-start" : "hidden",
      )}
    >
      <p className="absolute top-8 text-[9px] tracking-widest text-white/20">BIBLIOTHÈQUE</p>

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

      {/* Erreur */}
      {isAuthenticated && error && (
        <p className="mt-4 text-xs text-red-400/50">Impossible de charger les CVs.</p>
      )}
    </section>
  );
}
