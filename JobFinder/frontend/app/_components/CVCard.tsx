"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Trash2, X } from "lucide-react";

import { cn } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import type { CVData } from "@/lib/api/types";

type DeleteState = "idle" | "armed" | "closing" | "absorbing";

interface CVCardProps {
  cv: CVData;
  onDeleted: (id: string) => void;
  onSelect?: () => void;
  /** Highlights the card as the active CV (accent border + glow). */
  active?: boolean;
}

const delay = (ms: number) => new Promise<void>((res) => setTimeout(res, ms));
const CLOSING_MS = 120;

function AnimatedEllipsis() {
  const [step, setStep] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setStep((n) => (n % 3) + 1), 500);
    return () => clearInterval(id);
  }, []);
  return <span aria-hidden="true">{".".repeat(step)}</span>;
}

export default function CVCard({ cv, onDeleted, onSelect, active = false }: CVCardProps) {
  const isPending   = cv.status === "pending" || cv.status === "processing";
  const isSearching = cv.status === "done";
  const isError     = cv.status === "error";
  const showSpinner = isPending || isSearching;

  const displayName = cv.name ?? "CV sans nom";
  const date = new Date(cv.uploaded_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(null);
  const [cardHovered, setCardHovered]   = useState(false);
  const [trashHovered, setTrashHovered] = useState(false);
  const [deleteState, setDeleteState]   = useState<DeleteState>("idle");
  const [unseenCount, setUnseenCount]   = useState(cv.unseen_count);

  const isThumbnailLoading = cv.has_thumbnail && !thumbnailSrc;
  const showImageSpinner   = showSpinner || isThumbnailLoading;

  useEffect(() => {
    setUnseenCount(cv.unseen_count);
  }, [cv.unseen_count]);

  const wrapperRef      = useRef<HTMLDivElement>(null);
  const rowRef          = useRef<HTMLDivElement>(null);
  const cardRef         = useRef<HTMLDivElement>(null);
  const closingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!cv.has_thumbnail) return;

    let objectUrl: string | null = null;
    let cancelled = false;

    apiClient
      .get<Blob>(`/cv/${cv.id}/thumbnail`, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setThumbnailSrc(objectUrl);
      })
      .catch((error: unknown) => {
        const httpStatus = (error as { response?: { status?: number } })?.response?.status;
        if (httpStatus !== 404) console.error("cv thumbnail fetch failed", error);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [cv.id, cv.has_thumbnail]);

  useEffect(() => () => {
    if (closingTimerRef.current) clearTimeout(closingTimerRef.current);
  }, []);

  // Starts the reverse (rectangle) morph: side buttons + wire play their "out"
  // animation, then after CLOSING_MS the trash button itself shrinks back.
  const triggerCancel = () => {
    setDeleteState((prev) => (prev === "armed" ? "closing" : prev));
    closingTimerRef.current = setTimeout(() => {
      setDeleteState((prev) => (prev === "closing" ? "idle" : prev));
    }, CLOSING_MS);
  };

  // Close confirm state on click outside the trash row
  useEffect(() => {
    if (deleteState !== "armed") return;

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!wrapperRef.current?.contains(target) || !rowRef.current?.contains(target)) {
        triggerCancel();
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [deleteState]);

  const handleConfirmDelete = async () => {
    setDeleteState("absorbing");

    if (!cardRef.current) return;

    cardRef.current.style.transition = "transform 0.35s cubic-bezier(0.55,0,1,1), opacity 0.3s";
    cardRef.current.style.transform  = "scale(0)";
    cardRef.current.style.opacity    = "0";

    await delay(400);
    try {
      await apiClient.delete(`/cv/${cv.id}`);
    } catch (err) {
      console.error("cv delete failed", err);
      // Restore the card so the user can retry rather than silently losing it.
      if (cardRef.current) {
        cardRef.current.style.transition = "transform 0.3s ease-out, opacity 0.3s";
        cardRef.current.style.transform  = "";
        cardRef.current.style.opacity    = "";
      }
      setDeleteState("idle");
      return;
    }
    onDeleted(cv.id);
  };

  const handleCardClick = () => {
    if (deleteState === "armed") { triggerCancel(); return; }
    if (deleteState !== "idle") return;
    onSelect?.();
  };

  const confirming   = deleteState === "armed" || deleteState === "closing";
  const rowVisible   = (cardHovered || confirming) && deleteState !== "absorbing";
  // The icon sits a fixed 6px above the button's bottom edge (pb-[5px] + border),
  // so the button needs to clear the card by at least 20px (6 + the icon's own
  // 14px) before the icon is fully out from behind the card instead of being
  // cropped at the top. Keeping every visible state at/above that threshold
  // avoids the "cropped icon" look; trashHovered goes a bit further for a felt
  // reaction to hovering the icon itself.
  const rowY         = confirming ? 38 : cardHovered ? (trashHovered ? 26 : 20) : 20;
  const closing      = deleteState === "closing";

  return (
    <div
      ref={wrapperRef}
      className="relative h-full"
      onMouseEnter={() => setCardHovered(true)}
      onMouseLeave={() => setCardHovered(false)}
    >
      {/* Card */}
      <div
        ref={cardRef}
        onClick={handleCardClick}
        className={cn(
          "relative z-[2] flex h-full flex-col overflow-hidden rounded-[14px] bg-card p-[9px] cursor-pointer transition-[border-color,box-shadow] duration-150",
          active
            ? "border-[1.5px] border-accent shadow-[0_8px_26px_var(--bg-accent-muted)]"
            : "border border-subtle hover:border-soft hover:shadow-[0_6px_18px_rgba(0,0,0,.06)]",
        )}
      >
        {/* bg-card is a translucent tint (rgba) — on its own it doesn't hide
            the trash tab tucked behind the card (see delrow below), it just
            shows through it. This opaque backing sits under that tint, at the
            bottom of the stack, so the tint keeps its usual look but the card
            now actually occludes what's behind it. */}
        <div className="absolute inset-0 -z-10 rounded-[14px] bg-page" />

        <div
          role={showImageSpinner ? "status" : undefined}
          aria-label={
            isPending ? "Analyse en cours" :
            isSearching ? "Recherche en cours" :
            isThumbnailLoading ? "Chargement" :
            undefined
          }
          className={cn(
            "relative flex flex-1 min-h-0 items-center justify-center overflow-hidden rounded-[9px] border border-faint",
            !thumbnailSrc && showImageSpinner && "bg-card",
            !thumbnailSrc && !showImageSpinner && !isError && "bg-card-hover",
            isError && "bg-destructive-muted",
          )}
        >
          {thumbnailSrc && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumbnailSrc}
              alt=""
              className={cn(
                "absolute inset-0 h-full w-full object-cover",
                showSpinner && "grayscale opacity-50",
              )}
            />
          )}

          {thumbnailSrc && showSpinner && (
            <div className="absolute inset-0 bg-scrim" />
          )}

          {showImageSpinner && (
            <svg
              aria-hidden="true"
              className="relative h-5 w-5 animate-spin text-muted"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}

          {isError && <span className="text-xs text-destructive">Erreur</span>}
          {!showImageSpinner && !isError && !thumbnailSrc && (
            <span className="text-xs text-label">aperçu du CV</span>
          )}
        </div>

        <div className="flex-none pt-[11px] px-[5px] pb-[3px]">
          <p className="truncate text-[13.5px] font-normal text-strong" title={displayName}>{displayName}</p>
          <p className="mt-[3px] text-[12px] text-hint">{date}</p>

          {isPending && (
            <p className="mt-[9px] text-[12px] text-hint">Analyse en cours…</p>
          )}
          {isSearching && (
            <p className="mt-[9px] text-[12px] text-hint">
              Recherche en cours<AnimatedEllipsis />
            </p>
          )}
          {!showSpinner && !isError && (
            <div className="mt-[9px] flex items-center gap-[7px]">
              <span className="text-[12.5px] font-medium text-secondary">
                {cv.match_count} match{cv.match_count !== 1 ? "s" : ""}
              </span>
              <span
                title={unseenCount > 0 ? `+${unseenCount} correspondances depuis la dernière analyse` : "Analyse en attente"}
                className={cn(
                  "text-[11.5px] font-light tabular-nums",
                  unseenCount > 0 ? "text-success" : "text-label",
                )}
              >
                {unseenCount > 0 ? `+${unseenCount}` : "—"}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Delete controls: the trash button is a single persistent element that
          morphs between a bottom-tab rectangle and an armed circle. */}
      <div
        ref={rowRef}
        className="absolute left-0 right-0 bottom-0 flex items-center justify-center"
        style={{
          opacity: rowVisible ? 1 : 0,
          transform: `translateY(${rowY}px)`,
          pointerEvents: rowVisible ? "auto" : "none",
          // z-index only needs a transition-delay when freshly arming: without
          // it, the button jumps above the card the instant you click, while
          // it's still mid-flight (growing into the circle, sliding down) —
          // for a frame or two it visibly floats over the card artwork instead
          // of clearing it first. Delaying the flip until the move/resize is
          // basically done avoids that. No delay needed on the way back down:
          // dropping z-index immediately is what makes it tuck back behind the
          // card correctly.
          transition:
            deleteState === "armed"
              ? "opacity .16s ease, transform .3s cubic-bezier(.34,1.22,.64,1), z-index 0s .3s"
              : "opacity .16s ease, transform .3s cubic-bezier(.34,1.22,.64,1)",
          zIndex: confirming ? 9 : 1,
        }}
      >
        {confirming && (
          <button
            aria-label="Annuler la suppression"
            onClick={(e) => { e.stopPropagation(); triggerCancel(); }}
            className="flex flex-none h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-subtle bg-card text-secondary shadow-[0_8px_20px_rgba(0,0,0,.15)] transition-colors hover:bg-interactive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
            style={{ animation: closing ? "emgLOut .08s ease both" : "emgL .26s cubic-bezier(.34,1.42,.64,1) .12s both" }}
          >
            <X aria-hidden="true" width={14} height={14} strokeWidth={1.75} />
          </button>
        )}

        {/* Wire from cancel button to the trash button */}
        {confirming && (
          <div
            className="h-px w-[12.6px] flex-none rounded-full bg-[var(--border-soft)]"
            style={{
              transformOrigin: "right",
              animation: closing ? "lineOutH .08s ease both" : "lineInH .2s ease .04s both",
            }}
          />
        )}

        {/* Trash button gets its own positioning context so the card→trash
            wire is always centered on it, independent of its neighbors. */}
        <div className="relative flex flex-none">
          {/* Wire from card bottom edge to the trash button */}
          {confirming && (
            <div
              className="absolute bottom-full left-1/2 h-1 w-px -translate-x-1/2 rounded-full bg-[var(--border-soft)]"
              style={{
                transformOrigin: "top",
                animation: closing ? "lineOut .08s ease both" : "lineIn .2s ease .04s both",
              }}
            />
          )}

          <button
            aria-label="Supprimer ce CV"
            disabled={confirming}
            aria-disabled={confirming}
            onMouseEnter={() => setTrashHovered(true)}
            onMouseLeave={() => setTrashHovered(false)}
            onClick={(e) => {
              e.stopPropagation();
              if (deleteState === "idle") setDeleteState("armed");
            }}
            className={cn(
              "flex flex-none justify-center border transition-[width,height,border-radius,background-color,border-color,color] ease-out",
              confirming
                ? "h-[34px] w-[34px] items-center rounded-full border-transparent bg-solid-destructive text-on-solid shadow-[0_6px_16px_rgba(165,13,38,.42)] cursor-default duration-300"
                : cn(
                    "h-[30px] w-[54px] items-end pb-[5px] rounded-b-[10px] border-t-0 shadow-[0_7px_14px_rgba(0,0,0,.11)] cursor-pointer duration-150",
                    trashHovered
                      ? "border-solid-destructive-hover bg-solid-destructive-hover text-on-solid"
                      : "border-subtle bg-card text-hint",
                  ),
            )}
          >
            <Trash2 aria-hidden="true" width={14} height={14} strokeWidth={1.75} />
          </button>
        </div>

        {/* Wire from trash button to the confirm button */}
        {confirming && (
          <div
            className="h-px w-[12.6px] flex-none rounded-full bg-[var(--border-soft)]"
            style={{
              transformOrigin: "left",
              animation: closing ? "lineOutH .08s ease both" : "lineInH .2s ease .04s both",
            }}
          />
        )}

        {confirming && (
          <button
            aria-label="Confirmer la suppression"
            onClick={(e) => { e.stopPropagation(); void handleConfirmDelete(); }}
            className="flex flex-none h-[34px] w-[34px] items-center justify-center rounded-[10px] border-none bg-solid-confirm text-on-solid shadow-[0_8px_20px_rgba(47,158,68,.34)] transition-colors hover:bg-solid-confirm-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-confirm"
            style={{ animation: closing ? "emgROut .08s ease both" : "emgR .26s cubic-bezier(.34,1.42,.64,1) .12s both" }}
          >
            <Check aria-hidden="true" width={15} height={15} strokeWidth={2.25} />
          </button>
        )}
      </div>
    </div>
  );
}
