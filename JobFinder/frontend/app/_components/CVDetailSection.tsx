"use client";

import { forwardRef, useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { ChevronDown } from "lucide-react";
import apiClient from "@/lib/api/client";
import type { CVData, CVMatchesOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import CorrespondancesPanel from "./CorrespondancesPanel";
import CvAnalysisCard from "./CvAnalysisCard";

// Bornes du redimensionnement manuel de la zone d'analyse (drag sur le bandeau).
const ANALYSIS_MIN_HEIGHT_PX = 140;
const ANALYSIS_MAX_HEIGHT_RATIO = 0.8;
// En deçà de ce déplacement, un pointer down/up reste un clic (replier) ;
// au-delà, c'est un drag de redimensionnement et le clic qui suit est ignoré.
const DRAG_THRESHOLD_PX = 4;

interface Props {
  cvs: CVData[];
  selectedCvId: string;
  onCvChange: (id: string) => void;
  onClose: () => void;
  /** Bumped whenever the commune zone is saved elsewhere on the page — the
   * matches list is refetched to reflect the new geographic filter, since
   * this section stays mounted across zone changes (no route change). */
  zoneVersion?: number;
  /** Called whenever a match is marked seen, so the parent can refresh the
   * library's unseen_count badge for this CV. */
  onMatchSeen?: () => void;
}

const CVDetailSection = forwardRef<HTMLElement, Props>(
  ({ cvs, selectedCvId, onCvChange, onClose, zoneVersion, onMatchSeen }, ref) => {
    const currentIndex  = cvs.findIndex((cv) => cv.id === selectedCvId);
    const currentCv     = cvs[currentIndex] ?? null;
    const prevCv        = cvs[currentIndex - 1] ?? null;
    const nextCv        = cvs[currentIndex + 1] ?? null;

    const [matches, setMatches]               = useState<CVMatchesOut | null>(null);
    const [thumbnailSrc, setThumbnailSrc]     = useState<string | null>(null);
    const [loadingMatches, setLoadingMatches] = useState(true);
    const [matchesError, setMatchesError]     = useState<string | null>(null);
    const [analysisOpen, setAnalysisOpen]     = useState(true);
    // Hauteur choisie au drag — null tant que l'utilisateur n'a pas redimensionné
    // (la zone suit alors le cap CSS par défaut). Conservée entre replis/dépliages.
    const [analysisHeight, setAnalysisHeight] = useState<number | null>(null);
    const analysisBoxRef = useRef<HTMLDivElement>(null);
    const dragRef = useRef<{ startY: number; startHeight: number; maxHeight: number; moved: boolean } | null>(null);
    // Le navigateur émet un click après le pointerup — mémorise qu'un drag vient
    // d'avoir lieu pour que ce click-là ne replie pas la zone.
    const wasDragRef = useRef(false);

    const onBannerPointerDown = (e: ReactPointerEvent<HTMLButtonElement>) => {
      if (!analysisOpen) return; // repliée : simple clic pour déplier, pas de resize
      const box = analysisBoxRef.current;
      const column = box?.parentElement;
      if (!box || !column) return;
      dragRef.current = {
        startY: e.clientY,
        startHeight: box.getBoundingClientRect().height,
        maxHeight: column.clientHeight * ANALYSIS_MAX_HEIGHT_RATIO,
        moved: false,
      };
      // Optionnel : absent de jsdom, et garantit en navigateur que le drag
      // continue même si le pointeur sort du bandeau.
      e.currentTarget.setPointerCapture?.(e.pointerId);
    };

    const onBannerPointerMove = (e: ReactPointerEvent<HTMLButtonElement>) => {
      const drag = dragRef.current;
      if (!drag) return;
      const dy = drag.startY - e.clientY; // tirer vers le haut = agrandir
      if (!drag.moved && Math.abs(dy) < DRAG_THRESHOLD_PX) return;
      drag.moved = true;
      setAnalysisHeight(
        Math.min(drag.maxHeight, Math.max(ANALYSIS_MIN_HEIGHT_PX, drag.startHeight + dy)),
      );
    };

    const onBannerPointerUp = () => {
      wasDragRef.current = dragRef.current?.moved ?? false;
      dragRef.current = null;
    };

    const onBannerPointerCancel = () => {
      // Drag interrompu (ex. scroll tactile) — aucun click ne suivra, ne pas
      // armer wasDragRef sous peine d'avaler le prochain vrai clic.
      dragRef.current = null;
    };

    const onBannerClick = () => {
      if (wasDragRef.current) {
        wasDragRef.current = false;
        return;
      }
      setAnalysisOpen((o) => !o);
    };

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
    }, [selectedCvId, zoneVersion]);

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
        <div className="flex-none flex justify-center pt-[3px]">
          <button
            onClick={onClose}
            aria-label="Retour à la bibliothèque"
            className="flex flex-col items-center gap-1 bg-transparent border-0 p-0 cursor-pointer focus-visible:outline-none"
          >
            <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌃</span>
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

            {/* Analyse du CV — zone encadrée repliable, sous la vignette. Le bandeau
                (bouton) porte la flèche centrée en haut + le titre ; le cadre unique
                est porté ici, CvAnalysisCard n'a plus le sien. Un clic sur le bandeau
                replie/déplie ; maintenir et glisser verticalement redimensionne la
                zone (bornes ANALYSIS_MIN_HEIGHT_PX / ANALYSIS_MAX_HEIGHT_RATIO).
                Tant qu'aucun resize manuel n'a eu lieu, max-h-[69%] ≈ deux tiers de
                la colonne plafonne l'analyse (scroll interne au-delà) pour que la
                vignette (flex-1 min-h-0) reste toujours visible ; après un resize,
                la hauteur inline choisie s'applique, avec max-h-[80%] en garde-fou
                si la fenêtre rétrécit. */}
            <div
              ref={analysisBoxRef}
              style={analysisOpen && analysisHeight !== null ? { height: analysisHeight } : undefined}
              className={cn(
                "w-full shrink-0 flex flex-col min-h-0 rounded-xl border border-faint bg-chip overflow-hidden",
                analysisOpen && (analysisHeight === null ? "max-h-[69%]" : "max-h-[80%]"),
              )}
            >
              <button
                onClick={onBannerClick}
                onPointerDown={onBannerPointerDown}
                onPointerMove={onBannerPointerMove}
                onPointerUp={onBannerPointerUp}
                onPointerCancel={onBannerPointerCancel}
                aria-expanded={analysisOpen}
                aria-controls="cv-analysis-panel"
                className={cn(
                  "flex-none flex flex-col items-center gap-1 w-full bg-transparent border-0 py-2 select-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default",
                  analysisOpen ? "cursor-row-resize touch-none border-b border-faint" : "cursor-pointer",
                )}
              >
                {/* Flèche vers le haut quand repliée (déplier), vers le bas quand
                    ouverte (refermer) */}
                <ChevronDown
                  size={14}
                  className={cn("text-muted transition-transform", !analysisOpen && "rotate-180")}
                />
                <span className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted">
                  Analyse de votre CV
                </span>
              </button>
              {analysisOpen && (
                <div id="cv-analysis-panel" className="flex-1 min-h-0 overflow-y-auto">
                  <CvAnalysisCard cvId={selectedCvId} />
                </div>
              )}
            </div>
          </div>

          {/* Right — Vos correspondances, aligné sur le haut du pill */}
          <div className="flex-1 min-w-0 overflow-hidden flex flex-col pt-5">
            <CorrespondancesPanel
              key={selectedCvId}
              cvId={selectedCvId}
              matches={matches?.matches ?? []}
              loading={loadingMatches}
              error={matchesError}
              onMatchSeen={onMatchSeen}
            />
          </div>
        </div>
      </section>
    );
  },
);

CVDetailSection.displayName = "CVDetailSection";
export default CVDetailSection;
