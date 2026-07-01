"use client";

import { forwardRef, useCallback, useEffect, useState } from "react";
import apiClient from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { CVData, CVMatchesOut } from "@/lib/api/types";
import MatchList from "./MatchList";

interface Props {
  cvs: CVData[];
  selectedCvId: string;
  onCvChange: (id: string) => void;
  onClose: () => void;
}

const CVDetailSection = forwardRef<HTMLElement, Props>(
  ({ cvs, selectedCvId, onCvChange, onClose }, ref) => {
    const currentIndex  = cvs.findIndex((cv) => cv.id === selectedCvId);
    const currentCv     = cvs[currentIndex] ?? null;
    const [activeTab, setActiveTab]           = useState<"matches" | "review">("matches");
    const [matches, setMatches]               = useState<CVMatchesOut | null>(null);
    const [thumbnailSrc, setThumbnailSrc]     = useState<string | null>(null);
    const [loadingMatches, setLoadingMatches] = useState(true);
    const [matchesError, setMatchesError]     = useState<string | null>(null);

    useEffect(() => {
      setMatches(null);
      setMatchesError(null);
      setLoadingMatches(true);
      apiClient
        .get<CVMatchesOut>(`/matches/cv/${selectedCvId}`)
        .then((res) => setMatches(res.data))
        .catch((err: unknown) => {
          const status = (err as { response?: { status?: number } })?.response?.status;
          console.error("matches fetch failed", err);
          setMatchesError(status ? `Erreur ${status}` : "Erreur réseau");
        })
        .finally(() => setLoadingMatches(false));
    }, [selectedCvId]);

    useEffect(() => {
      if (!currentCv?.has_thumbnail) { setThumbnailSrc(null); return; }
      let objectUrl: string | null = null;
      let cancelled = false;
      apiClient
        .get<Blob>(`/cv/${selectedCvId}/thumbnail`, { responseType: "blob" })
        .then((res) => {
          if (cancelled) return;
          objectUrl = URL.createObjectURL(res.data);
          setThumbnailSrc(objectUrl);
        })
        .catch(() => setThumbnailSrc(null));
      return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
    }, [selectedCvId, currentCv?.has_thumbnail]);

    const goToCv = useCallback((id: string) => {
      setActiveTab("matches");
      onCvChange(id);
    }, [onCvChange]);

    const prevCv = cvs[currentIndex - 1] ?? null;
    const nextCv = cvs[currentIndex + 1] ?? null;

    return (
      <section
        ref={ref}
        id="cv-detail"
        className="relative h-dvh snap-start bg-page flex flex-col"
      >
        {/* Left edge — previous CV */}
        <button
          onClick={() => prevCv && goToCv(prevCv.id)}
          disabled={!prevCv}
          aria-label="CV précédent"
          className="absolute left-0 inset-y-0 z-10 w-10 flex items-center justify-center text-muted hover:text-body hover:bg-interactive disabled:opacity-0 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          ←
        </button>

        {/* Right edge — next CV */}
        <button
          onClick={() => nextCv && goToCv(nextCv.id)}
          disabled={!nextCv}
          aria-label="CV suivant"
          className="absolute right-0 inset-y-0 z-10 w-10 flex items-center justify-center text-muted hover:text-body hover:bg-interactive disabled:opacity-0 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          →
        </button>

        {/* BIBLIOTHÈQUE back indicator */}
        <button
          onClick={onClose}
          className="absolute top-6 left-1/2 z-10 flex -translate-x-1/2 flex-col items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default rounded"
        >
          <span className="animate-bounce text-sm text-hint">⌃</span>
          <span className="text-[9px] tracking-widest text-label">BIBLIOTHÈQUE</span>
        </button>

        {/* Pagination dots — pushed down to create breathing room below indicator */}
        <div className="flex items-center justify-center pt-44">
          <div className="flex gap-1.5">
            {cvs.map((cv, i) => (
              <button
                key={cv.id}
                aria-label={`Aller au CV ${i + 1}`}
                onClick={() => goToCv(cv.id)}
                className={cn(
                  "h-1.5 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                  i === currentIndex ? "w-4 bg-dot-active" : "w-1.5 bg-interactive-hover",
                )}
              />
            ))}
          </div>
        </div>

        {/* Main content — top border closes the entire zone (image + tabs) */}
        <div className="flex flex-1 overflow-hidden mt-6 border-t border-faint">

          {/* Left — CV name + thumbnail */}
          <div className="w-[38%] border-r border-faint flex flex-col p-8 gap-3">
            <p className="shrink-0 text-center text-[11px] text-secondary truncate">
              {currentCv?.name ?? "CV"}
            </p>
            <div className="flex-1 flex items-center justify-center">
              {thumbnailSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={thumbnailSrc}
                  alt="Aperçu du CV"
                  className="h-full w-full object-contain rounded-lg"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center rounded-lg bg-card border border-faint">
                  <span className="text-xs text-label">PDF</span>
                </div>
              )}
            </div>
          </div>

          {/* Right — Tabs + content */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex gap-6 px-8 pt-6 pb-0 border-b border-faint">
              {(["matches", "review"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "pb-3 text-xs tracking-wide transition-colors capitalize border-b-2 -mb-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                    activeTab === tab
                      ? "text-primary border-active"
                      : "text-hint border-transparent hover:text-muted",
                  )}
                >
                  {tab === "matches" ? "Matchs" : "Review"}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto px-8 py-6">
              {activeTab === "matches" && (
                matchesError
                  ? <p className="text-xs text-destructive mt-8 text-center">{matchesError} — impossible de charger les matchs</p>
                  : <MatchList matches={matches?.matches ?? []} loading={loadingMatches} romeCodesDict={matches?.rome_codes ?? {}} />
              )}
              {activeTab === "review" && (
                <p className="text-xs text-label mt-8 text-center">Bientôt disponible</p>
              )}
            </div>
          </div>
        </div>
      </section>
    );
  }
);

CVDetailSection.displayName = "CVDetailSection";
export default CVDetailSection;
