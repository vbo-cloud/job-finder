"use client";

import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated } from "@azure/msal-react";
import posthog from "posthog-js";

import apiClient from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { TOTAL_LIBRARY_SLOTS, UNLOCKED_CV_SLOTS } from "@/lib/cvSlots";
import type { CVData } from "@/lib/api/types";

import CVCard from "./CVCard";
import CVCardLocked from "./CVCardLocked";
import CVCardOptimistic from "./CVCardOptimistic";
import CVCardPlaceholder from "./CVCardPlaceholder";
import CVCardSkeleton from "./CVCardSkeleton";
import ScrollHint from "./ScrollHint";

const POLL_INTERVAL_MS = 3000;

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
  /** Scrolls to the home/upload section ("ACCUEIL" hint) — owned by the
   * parent so this component doesn't need to know about a sibling's DOM id. */
  onScrollToHome?: () => void;
  /** Scrolls to the detail section ("OFFRES" hint) — owned by the parent for
   * the same reason as onScrollToHome. */
  onScrollToOffers?: () => void;
  /** Scrolls to the home section and opens its file picker there — owned by
   * the parent so this component doesn't need its own upload pipeline; the
   * upload and its animation are handled by UploadSection. */
  onAddCv?: () => void;
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
  onAddCv,
}: Props) {
  const isAuthenticated        = useIsAuthenticated();
  const [cvs, setCvs]          = useState<CVData[]>([]);
  const [loading, setLoading]  = useState(true);
  const [error, setError]      = useState(false);

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

  // Person property (not an event counter) so a PostHog "breakdown by person
  // property" insight can list every distinct CV count without any code or
  // graph change when the unlocked-slot cap moves. Depends on cvs.length, not
  // cvs, so the 3s poll (above) doesn't re-post the same value on every tick
  // while a CV is still pending/processing/done. The loading guard avoids
  // writing a premature current_cv_count: 0 before the first fetch resolves —
  // though it doesn't cover every zero: if fetchCvs's retry also fails, cvs
  // stays [] and loading still flips to false in its finally, so this does
  // post 0 for a user whose fetch is erroring, same as a genuine empty library.
  // Two alternatives were considered and rejected: counting cv_uploaded events
  // (already tracked in UploadSection.tsx) per user breaks the moment a
  // deletion happens — upload → delete → re-upload reads as 2 CVs for someone
  // who only ever holds 1; and a one-off "blocked at cap" event (dropped from
  // the earlier slot-lock prompt) only fires for users already at the cap, so
  // it says nothing about the 1-vs-2 distribution across everyone else.
  useEffect(() => {
    if (!isAuthenticated || loading) return;
    posthog.setPersonProperties({ current_cv_count: cvs.length });
  }, [cvs.length, isAuthenticated, loading]);

  // When showing the optimistic card, it occupies the first slot; real CVs fill the rest.
  // This slice is a display-only cap: any account that already held more than
  // UNLOCKED_CV_SLOTS CVs before this cap existed keeps every excess CV server-side —
  // their embedding and ROME extraction were one-off costs already paid at upload time,
  // but they keep being matched daily by the matching agent (which iterates every CV
  // with an embedding regardless of this constant, see agents/matching/main.py) and
  // keep enqueuing their own top-N match_analyses each run — the recurring LLM cost
  // this cap is meant to reduce. Only the library grid and the "x / N" badge below
  // stop showing them; there is no reconciliation/archival step, and the two caps
  // (see MAX_CVS_PER_USER in shared/constants.py) only ever block *new* uploads.
  // Intentional: the cost reduction this cap buys only applies going forward, not
  // retroactively to CVs uploaded before it existed.
  const optimisticCount   = showOptimistic ? 1 : 0;
  const realCvs            = showOptimistic ? cvs.slice(0, UNLOCKED_CV_SLOTS - 1) : cvs.slice(0, UNLOCKED_CV_SLOTS);
  const used               = optimisticCount + realCvs.length;
  const canAdd             = used < UNLOCKED_CV_SLOTS;
  const emptyUnlockedCount = Math.max(0, UNLOCKED_CV_SLOTS - used - (canAdd ? 1 : 0));
  const lockedCount        = Math.max(0, TOTAL_LIBRARY_SLOTS - UNLOCKED_CV_SLOTS);
  const showGrid           = showOptimistic || cvs.length > 0;

  // "ACCUEIL" hint: scroll home.
  const handleAccueilClick = () => onScrollToHome?.();

  return (
    <section
      id="library"
      className={cn(
        // md:ml-24 clears LeftNavRail (fixed left-4, ~52px wide, plus breathing room) — must stay ≥ its right edge.
        "relative h-dvh bg-page flex flex-col md:ml-24",
        accessible ? "snap-start" : "hidden",
      )}
    >
      {/* Scroll hints — meaningless below md, where swipe navigation is off
          (the pinned mobile menu navigates instead) and the bar covers the top. */}
      <ScrollHint
        direction="up"
        label="ACCUEIL"
        ariaLabel="Retour à l'accueil"
        onClick={handleAccueilClick}
        className="absolute top-[18px] left-1/2 -translate-x-1/2 max-md:hidden"
      />

      {/* Hidden without a selected CV: the detail section it scrolls to
          isn't mounted yet (HomeClient only renders it once selectedCvId is
          set), so the click would silently no-op otherwise. */}
      {selectedCvId && (
        <ScrollHint
          direction="down"
          label="OFFRES"
          ariaLabel="Voir les offres"
          onClick={onScrollToOffers}
          className="absolute bottom-[18px] left-1/2 -translate-x-1/2 max-md:hidden"
        />
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
                De nouvelles offres sont recherchées chaque jour à 18h pour chacun de vos CVs.
              </p>
            </div>
            <div className="flex flex-none items-center gap-[9px]">
              <span className="text-[9px] tracking-widest text-label">CV IMPORTÉS</span>
              <span className="text-[9px] tracking-widest text-label">
                {Math.min(cvs.length, UNLOCKED_CV_SLOTS)} / {UNLOCKED_CV_SLOTS}
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
                {Array.from({ length: TOTAL_LIBRARY_SLOTS }).map((_, i) => <CVCardSkeleton key={i} />)}
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
                    onClick={onAddCv}
                    aria-label="Ajouter un CV"
                    className={cn(
                      "flex h-full flex-col items-center justify-center gap-[11px] rounded-[14px] border-[1.5px] border-dashed border-soft bg-transparent text-hint transition-colors",
                      "cursor-pointer hover:border-accent hover:bg-accent-muted hover:text-accent",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                    )}
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-[1.5px] border-current pb-[2px] text-[22px] leading-none">+</div>
                    <span className="text-[13px] font-semibold">Ajouter un CV</span>
                  </button>
                )}
                {Array.from({ length: emptyUnlockedCount }).map((_, i) => (
                  <CVCardPlaceholder key={`placeholder-${i}`} />
                ))}
                {Array.from({ length: lockedCount }).map((_, i) => (
                  <CVCardLocked key={`locked-${i}`} />
                ))}
              </div>
            )}

            {isAuthenticated && error && (
              <p className="mt-4 text-xs text-destructive">Impossible de charger les CVs.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
