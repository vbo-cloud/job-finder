"use client";

import { forwardRef, useCallback, useEffect, useState } from "react";
import apiClient from "@/lib/api/client";
import type { CVData, CVMatchesOut } from "@/lib/api/types";
import CorrespondancesPanel from "./CorrespondancesPanel";

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
    const prevCv        = cvs[currentIndex - 1] ?? null;
    const nextCv        = cvs[currentIndex + 1] ?? null;

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
        .get<Blob>(`/cv/${selectedCvId}/thumbnail?size=lg`, { responseType: "blob" })
        .then((res) => {
          if (cancelled) return;
          objectUrl = URL.createObjectURL(res.data);
          setThumbnailSrc(objectUrl);
        })
        .catch(() => setThumbnailSrc(null));
      return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
    }, [selectedCvId, currentCv?.has_thumbnail]);

    const goToCv = useCallback((id: string) => { onCvChange(id); }, [onCvChange]);

    return (
      <section
        ref={ref}
        id="cv-detail"
        className="h-dvh snap-start bg-page flex flex-col"
      >
        {/* BIBLIOTHÈQUE — dans le flux, centré, pousse le body en dessous */}
        <div className="flex-none flex justify-center pt-1.5">
          <button
            onClick={onClose}
            aria-label="Retour à la bibliothèque"
            className="flex flex-col items-center gap-1 bg-transparent border-0 p-0 cursor-pointer focus-visible:outline-none"
          >
            <span className="animate-bounce text-sm text-hint">⌃</span>
            <span className="text-[9px] tracking-widest text-label">BIBLIOTHÈQUE</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left — CV thumbnail */}
          <div className="w-[38%] border-r border-faint flex flex-col items-center gap-4 px-6 pt-5 pb-6 overflow-hidden">
            {/* Document selector — +50% */}
            <div className="flex items-center gap-2 bg-chip border border-faint rounded-full py-[6px] pl-[18px] pr-[6px] shrink-0">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted shrink-0">
                <path d="M14 3v5h5M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
              </svg>
              <span className="text-[13px] text-body font-medium max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap">
                {currentCv?.name ?? "CV"}
              </span>
              <span className="font-mono text-[11px] text-muted tabular-nums">
                {currentIndex + 1}/{cvs.length}
              </span>
              <button
                onClick={() => prevCv && goToCv(prevCv.id)}
                disabled={!prevCv}
                aria-label="CV précédent"
                className="flex h-[36px] w-[36px] items-center justify-center rounded-full bg-page text-body text-[18px] disabled:opacity-0 hover:text-strong transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default"
              >
                ‹
              </button>
              <button
                onClick={() => nextCv && goToCv(nextCv.id)}
                disabled={!nextCv}
                aria-label="CV suivant"
                className="flex h-[36px] w-[36px] items-center justify-center rounded-full bg-page text-body text-[18px] disabled:opacity-0 hover:text-strong transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default"
              >
                ›
              </button>
            </div>

            {/* Thumbnail — fits entirely, no scroll */}
            <div className="flex-1 min-h-0 flex items-center justify-center w-full">
              {thumbnailSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={thumbnailSrc}
                  alt="Aperçu du CV"
                  className="max-h-full max-w-full object-contain rounded-sm border border-black/20"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center rounded-sm border border-black/20 bg-card">
                  <span className="text-xs text-label">PDF</span>
                </div>
              )}
            </div>
          </div>

          {/* Right — Vos correspondances, aligné sur le haut du pill */}
          <div className="flex-1 min-w-0 overflow-hidden flex flex-col pt-5">
            <CorrespondancesPanel
              matches={matches?.matches ?? []}
              loading={loadingMatches}
              error={matchesError}
            />
          </div>
        </div>
      </section>
    );
  },
);

CVDetailSection.displayName = "CVDetailSection";
export default CVDetailSection;
