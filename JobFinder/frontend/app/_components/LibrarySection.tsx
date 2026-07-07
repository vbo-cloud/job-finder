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

const GRID_CLASSES =
  "grid gap-x-[18px] gap-y-[52px] [grid-template-columns:repeat(auto-fill,minmax(180px,1fr))] [grid-auto-rows:352px]";

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
}

export default function LibrarySection({
  refreshTrigger = 0,
  onAccessibilityChange,
  optimisticUpload,
  onOptimisticConsumed,
  onCvSelect,
  onCvsChange,
  selectedCvId = null,
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
      onCvsChange?.(data);
      setError(false);
    } catch (err) {
      console.error("[LibrarySection] fetch failed", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [onCvsChange]);

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
  // actually landed — "scrollend" covers both the animated case and
  // prefers-reduced-motion (an instant jump still fires it); the timeout is
  // only a safety net for the rare browser without scrollend support.
  const handleAddClick = () => {
    const home = document.getElementById("home");
    const scrollContainer = home?.closest("main");
    if (!home || !scrollContainer) {
      fileInputRef.current?.click();
      return;
    }
    let opened = false;
    const openPicker = () => {
      if (opened) return;
      opened = true;
      scrollContainer.removeEventListener("scrollend", openPicker);
      fileInputRef.current?.click();
    };
    scrollContainer.addEventListener("scrollend", openPicker, { once: true });
    setTimeout(openPicker, 900);
    home.scrollIntoView({ behavior: "smooth" });
  };

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
      <div className="pointer-events-none absolute top-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1">
        <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌃</span>
        <span className="text-[9px] tracking-widest text-label">ACCUEIL</span>
      </div>

      <div className="pointer-events-none absolute bottom-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1">
        <span className="text-[9px] tracking-widest text-label">CORRESPONDANCES</span>
        <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌄</span>
      </div>

      {/* Header is taken out of flow (absolute) so its own vertical offset
          doesn't push the grid below down — the grid stays centered in the
          full section regardless of how far down the header sits. */}
      <div className="absolute inset-x-0 top-0 px-10 pt-40">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="flex items-end justify-between gap-5">
            <div className="min-w-0">
              <h1 className="m-0 text-[22px] font-normal tracking-[-0.015em] leading-[1.05] text-strong">Bibliothèque</h1>
              <p className="mt-[9px] text-[13.5px] text-hint">Sélectionnez un CV pour visualiser ses correspondances.</p>
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

      <div className="flex-1 min-h-0 overflow-y-auto px-10 pb-16 [scrollbar-gutter:stable_both-edges]">
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
