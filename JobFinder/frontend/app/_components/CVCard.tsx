"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import type { CVData } from "@/lib/api/types";

type DeleteState = "idle" | "confirm" | "absorbing";

interface CVCardProps {
  cv: CVData;
  onDeleted: (id: string) => void;
}

const delay = (ms: number) => new Promise<void>((res) => setTimeout(res, ms));

export default function CVCard({ cv, onDeleted }: CVCardProps) {
  const isPending   = cv.status === "pending" || cv.status === "processing";
  const isError     = cv.status === "error";
  const displayName = cv.name ?? "CV sans nom";
  const date = new Date(cv.uploaded_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(null);
  const [isHovered, setIsHovered]       = useState(false);
  const [deleteState, setDeleteState]   = useState<DeleteState>("idle");

  const cardRef = useRef<HTMLDivElement>(null);
  const holeRef = useRef<HTMLDivElement>(null);

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
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status !== 404) console.error("cv thumbnail fetch failed", error);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [cv.id, cv.has_thumbnail]);

  const handleConfirmDelete = async () => {
    setDeleteState("absorbing");

    if (!holeRef.current || !cardRef.current) return;

    // 1. Black hole grows at the centre of the card
    holeRef.current.style.transition = "width 0.3s ease-out, height 0.3s ease-out, opacity 0.3s";
    holeRef.current.style.width      = "120px";
    holeRef.current.style.height     = "120px";
    holeRef.current.style.opacity    = "1";

    // 2. Card contracts toward the centre
    await delay(300);
    cardRef.current.style.transition = "transform 0.4s cubic-bezier(0.55,0,1,1), opacity 0.3s 0.1s";
    cardRef.current.style.transform  = "scale(0)";
    cardRef.current.style.opacity    = "0";

    // 3. Black hole fades out
    await delay(350);
    holeRef.current.style.transition = "opacity 0.2s";
    holeRef.current.style.opacity    = "0";

    // 4. API call then remove card from the list
    await delay(200);
    try {
      await apiClient.delete(`/cv/${cv.id}`);
    } catch (err) {
      console.error("cv delete failed", err);
    }
    onDeleted(cv.id);
  };

  const showControls = (isHovered || deleteState !== "idle") && deleteState !== "absorbing";

  return (
    <div
      className="flex w-44 flex-shrink-0 flex-col"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Card */}
      <div
        ref={cardRef}
        className="relative flex flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-4"
      >
        <div
          role={isPending ? "status" : undefined}
          aria-label={isPending ? "Analyse en cours" : undefined}
          className={cn(
            "relative flex aspect-[3/4] w-full items-center justify-center overflow-hidden rounded-lg",
            !thumbnailSrc && isPending && "bg-white/[0.05]",
            !thumbnailSrc && !isPending && !isError && "bg-white/[0.08]",
            isError && "bg-red-500/[0.08]",
          )}
        >
          {thumbnailSrc && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumbnailSrc}
              alt=""
              className={cn(
                "absolute inset-0 h-full w-full object-cover",
                isPending && "grayscale opacity-50",
              )}
            />
          )}

          {thumbnailSrc && isPending && (
            <div className="absolute inset-0 bg-black/40" />
          )}

          {isPending && (
            <svg
              aria-hidden="true"
              className="relative h-5 w-5 animate-spin text-white/35"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}

          {isError && <span className="text-xs text-red-400/60">Erreur</span>}
          {!isPending && !isError && !thumbnailSrc && (
            <span className="text-xs text-white/20">PDF</span>
          )}
        </div>

        <p className="truncate text-[11px] text-white/55" title={displayName}>{displayName}</p>
        <p className="text-[10px] text-white/25">{date}</p>

        {isPending && (
          <p className="text-[10px] text-white/25">Analyse en cours…</p>
        )}
        {!isPending && !isError && (
          <p className="text-[10px] text-white/35">
            {cv.match_count} match{cv.match_count !== 1 ? "s" : ""}
          </p>
        )}

        {/* Black hole overlay — animated imperatively in handleConfirmDelete */}
        <div
          ref={holeRef}
          aria-hidden="true"
          style={{ width: 0, height: 0, opacity: 0 }}
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-black"
        />
      </div>

      {/* Delete controls — wire + trash button + sub-icons */}
      <div
        className={cn(
          "flex flex-col items-center transition-opacity duration-150",
          showControls ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      >
        {/* Vertical wire from card to trash */}
        <div className="mx-auto h-3.5 w-px bg-white/20" />

        {/* Trash button */}
        <button
          aria-label="Supprimer ce CV"
          onClick={() => setDeleteState("confirm")}
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-full bg-red-600 transition-colors hover:bg-red-400 active:bg-red-800",
            deleteState === "confirm" && "bg-red-800",
          )}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-3.5 w-3.5 text-white"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
            />
          </svg>
        </button>

        {/* Sub-icons — cancel (X) and confirm (check) */}
        {deleteState === "confirm" && (
          <div className="flex gap-8 animate-[fadeSlideDown_200ms_ease-out_both]">
            {/* Cancel */}
            <div className="flex flex-col items-center gap-0">
              <div className="h-2.5 w-px bg-white/20" />
              <button
                aria-label="Annuler la suppression"
                onClick={() => setDeleteState("idle")}
                className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 transition-colors hover:bg-white/20 active:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="h-3 w-3 text-white/70"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Confirm */}
            <div className="flex flex-col items-center gap-0">
              <div className="h-2.5 w-px bg-white/20" />
              <button
                aria-label="Confirmer la suppression"
                onClick={() => void handleConfirmDelete()}
                className="flex h-6 w-6 items-center justify-center rounded-full bg-green-800 transition-colors hover:bg-green-600 active:bg-green-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="h-3 w-3 text-white"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
