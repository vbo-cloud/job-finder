"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
const MAX_PDF_BYTES = 10 * 1024 * 1024;

// Mobile-first: narrower minimum column and shorter rows so a 375px screen
// fits two card columns instead of one card stretched full-width; the desktop
// values are restored from md: up (unchanged rendering ≥768px). 130px: after
// px-4 and the two reserved scrollbar gutters, a 375px viewport leaves ~294px
// for the grid — two columns need min ≤ (294 - 18px gap) / 2 = 138px.
const GRID_CLASSES =
  "grid gap-x-[18px] gap-y-[52px] [grid-template-columns:repeat(auto-fill,minmax(130px,1fr))] [grid-auto-rows:300px] md:[grid-template-columns:repeat(auto-fill,minmax(180px,1fr))] md:[grid-auto-rows:352px]";

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
  /** Called when the user clicks a CV card to open its detail view. */
  onCvSelect?: (id: string) => void;
  /** Called after each successful fetch so the parent can keep a mirror of the CV list. */
  onCvsChange?: (cvs: CVData[]) => void;
  /** The CV currently shown in the detail section — highlighted with the accent border. */
  selectedCvId?: string | null;
  /** Scrolls to the home/upload section; calls onLanded once the scroll has
   * settled (or immediately if the scroll can't be determined). Owned by the
   * parent so this component doesn't need to know about a sibling's DOM id. */
  onScrollToHome?: (onLanded: () => void) => void;
  /** Scrolls to the detail section ("OFFRES" hint) — owned by the parent for
   * the same reason as onScrollToHome. */
  onScrollToOffers?: () => void;
}

export default function LibrarySection({
  refreshTrigger = 0,
  onAccessibilityChange,
  optimisticUpload,
  onOptimisticConsumed,
  onCvSelect,
  onCvsChange,
  selectedCvId = null,
  onScrollToHome,
  onScrollToOffers,
}: Props) {
  const isAuthenticated        = useIsAuthenticated();
  const [cvs, setCvs]          = useState<CVData[]>([]);
  const [loading, setLoading]  = useState(true);
  const [error, setError]      = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef           = useRef<HTMLInputElement>(null);
  const uploadErrorTimerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (uploadErrorTimerRef.current) clearTimeout(uploadErrorTimerRef.current);
  }, []);

  const handleCvDeleted = useCallback((id: string) => {
    setCvs((prev) => prev.filter((cv) => cv.id !== id));
  }, []);

  // Mirror every cvs change to the parent — fetches AND local deletions. A
  // stale parent copy kept the detail section mounted (and the correspondances
  // view reachable) after the last CV was deleted.
  useEffect(() => {
    onCvsChange?.(cvs);
  }, [cvs, onCvsChange]);

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
      (cv) =>
        cv.status === "pending" ||
        cv.status === "processing" ||
        cv.status === "done",
    );
    if (!hasPending) return;

    const id = setInterval(() => void fetchCvs(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [cvs, fetchCvs, isAuthenticated]);

  // When showing the optimistic card, it occupies the first slot; real CVs fill the rest.
  const optimisticCount  = showOptimistic ? 1 : 0;
  const realCvs           = showOptimistic ? cvs.slice(0, MAX_CVS - 1) : cvs.slice(0, MAX_CVS);
  const used              = optimisticCount + realCvs.length;
  const canAdd            = used < MAX_CVS;
  const placeholderCount  = Math.max(0, MAX_CVS - used - (canAdd ? 1 : 0));
  const showGrid          = showOptimistic || cvs.length > 0;

  // Scroll back up to the map/upload section first so the file picker opens
  // in a familiar context, then trigger the browse dialog once the scroll has
  // landed. The scroll itself (and knowledge of the home section's DOM id)
  // belongs to the parent — this component only asks to be told when it's safe.
  const handleAddClick = () => {
    if (!onScrollToHome) { fileInputRef.current?.click(); return; }
    onScrollToHome(() => fileInputRef.current?.click());
  };

  // "ACCUEIL" hint: same scroll, no follow-up action once landed.
  const handleAccueilClick = () => onScrollToHome?.(() => {});

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (uploadErrorTimerRef.current) clearTimeout(uploadErrorTimerRef.current);
    if (file.type !== "application/pdf") {
      setUploadError("Le fichier doit être un PDF.");
      uploadErrorTimerRef.current = setTimeout(() => setUploadError(null), 4000);
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setUploadError("Le fichier dépasse la taille maximale autorisée (10 Mo).");
      uploadErrorTimerRef.current = setTimeout(() => setUploadError(null), 4000);
      return;
    }
    setUploadError(null);

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiClient.post("/cv/upload", formData);
      await fetchCvs();
    } catch (err) {
      console.error("[LibrarySection] add CV failed", err);
      setUploadError("Échec de l'import, réessayez.");
      uploadErrorTimerRef.current = setTimeout(() => setUploadError(null), 4000);
    } finally {
      setUploading(false);
    }
  }, [fetchCvs]);

  return (
    <section
      id="library"
      className={cn(
        "relative h-dvh bg-page flex flex-col",
        accessible ? "snap-start" : "hidden",
      )}
    >
      {/* Scroll hints — meaningless below md, where swipe navigation is off
          (the pinned mobile menu navigates instead) and the bar covers the top. */}
      <button
        type="button"
        onClick={handleAccueilClick}
        aria-label="Retour à l'accueil"
        className="absolute top-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 bg-transparent border-0 p-0 cursor-pointer max-md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌃</span>
        <span className="text-[9px] tracking-widest text-label">ACCUEIL</span>
      </button>

      {/* Hidden without a selected CV: the detail section it scrolls to
          isn't mounted yet (HomeClient only renders it once selectedCvId is
          set), so the click would silently no-op otherwise. */}
      {selectedCvId && (
        <button
          type="button"
          onClick={onScrollToOffers}
          aria-label="Voir les offres"
          className="absolute bottom-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 bg-transparent border-0 p-0 cursor-pointer max-md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          <span className="text-[9px] tracking-widest text-label">OFFRES</span>
          <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌄</span>
        </button>
      )}

      {/* Header is taken out of flow (absolute) so its own vertical offset
          doesn't push the grid below down — the grid stays centered in the
          full section regardless of how far down the header sits.
          pointer-events-none: this box's top edge sits at inset-x-0 top-0,
          overlapping the ACCUEIL hint button above — nothing inside it is
          interactive, so it must not intercept that click. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 px-4 pt-24 md:px-10 md:pt-40">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="flex items-end justify-between gap-5">
            <div className="min-w-0">
              <h1 className="m-0 text-[22px] font-normal tracking-[-0.015em] leading-[1.05] text-strong">Bibliothèque</h1>
              <p className="mt-[9px] text-[13.5px] text-hint">
                De nouvelles offres sont recherchées chaque jour à 12h et 20h pour chacun de vos CVs.
              </p>
            </div>
            <div className="flex flex-none items-center gap-[9px]">
              <span className="text-[9px] tracking-widest text-label">CV IMPORTÉS</span>
              <span className="text-[9px] tracking-widest text-label">
                {Math.min(cvs.length, MAX_CVS)} / {MAX_CVS}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-16 [scrollbar-gutter:stable_both-edges] md:px-10">
        {/* min-h-full + justify-center vertically centers short content without
            the classic flex-centering bug where overflow gets clipped at the
            top when there are enough CVs to fill more than one viewport. */}
        <div className="min-h-full flex flex-col justify-center">
          <div className="mx-auto w-full max-w-[1080px]">

            {/* Skeleton only on initial load, before any CV (real or optimistic) is known */}
            {loading && !showGrid && (
              <div className={GRID_CLASSES}>
                {Array.from({ length: 10 }).map((_, i) => <CVCardSkeleton key={i} />)}
              </div>
            )}

            {/* Grid: optimistic slot + real CVs + add slot + empty placeholders */}
            {showGrid && (
              <div className={GRID_CLASSES}>
                {showOptimistic && (
                  <CVCardOptimistic thumbnailUrl={optimisticUpload!.thumbnailUrl} />
                )}
                {realCvs.map((cv) => (
                  <CVCard
                    key={cv.id}
                    cv={cv}
                    onDeleted={handleCvDeleted}
                    onSelect={() => onCvSelect?.(cv.id)}
                    active={cv.id === selectedCvId}
                  />
                ))}
                {canAdd && (
                  <button
                    type="button"
                    onClick={handleAddClick}
                    disabled={uploading}
                    aria-busy={uploading}
                    aria-label={uploading ? "Import du CV en cours" : "Ajouter un CV"}
                    className={cn(
                      "flex h-full flex-col items-center justify-center gap-[11px] rounded-[14px] border-[1.5px] border-dashed border-soft bg-transparent text-hint transition-colors",
                      uploading ? "cursor-wait opacity-60" : "cursor-pointer hover:border-accent hover:bg-accent-muted hover:text-accent",
                    )}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-[1.5px] border-current pb-[2px] text-[22px] leading-none">+</div>
                    <span className="text-[13px] font-semibold">{uploading ? "Import en cours…" : "Ajouter un CV"}</span>
                  </button>
                )}
                {Array.from({ length: placeholderCount }).map((_, i) => (
                  <CVCardPlaceholder key={`placeholder-${i}`} />
                ))}
              </div>
            )}

            {isAuthenticated && error && (
              <p className="mt-4 text-xs text-destructive">Impossible de charger les CVs.</p>
            )}

            {uploadError && (
              <p role="alert" className="mt-4 text-xs text-destructive">{uploadError}</p>
            )}
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="sr-only"
        onChange={(e) => void handleFileChange(e)}
      />
    </section>
  );
}
