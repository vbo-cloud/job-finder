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

  const [thumbnailSrc, setThumbnailSrc]   = useState<string | null>(null);
  const [isHovered, setIsHovered]         = useState(false);
  const [deleteState, setDeleteState]     = useState<DeleteState>("idle");
  const [unseenCount, setUnseenCount] = useState(cv.unseen_count);

  useEffect(() => {
    setUnseenCount(cv.unseen_count);
  }, [cv.unseen_count]);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const rowRef     = useRef<HTMLDivElement>(null);
  const cardRef    = useRef<HTMLDivElement>(null);

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

  // Close confirm state on click outside the trash row
  useEffect(() => {
    if (deleteState !== "confirm") return;

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!wrapperRef.current?.contains(target)) {
        setDeleteState("idle");
        return;
      }
      if (!rowRef.current?.contains(target)) {
        setDeleteState("idle");
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

  const showControls = (isHovered || deleteState !== "idle") && deleteState !== "absorbing";

  return (
    <div
      ref={wrapperRef}
      className="flex w-44 flex-shrink-0 flex-col"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Card */}
      <div
        ref={cardRef}
        className="flex flex-col gap-2.5 rounded-xl border border-subtle bg-card p-4"
      >
        <div
          role={isPending ? "status" : undefined}
          aria-label={isPending ? "Analyse en cours" : undefined}
          className={cn(
            "relative flex aspect-[3/4] w-full items-center justify-center overflow-hidden rounded-lg",
            !thumbnailSrc && isPending && "bg-card",
            !thumbnailSrc && !isPending && !isError && "bg-card-hover",
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
          {!isPending && !isError && !thumbnailSrc && (
            <span className="text-xs text-label">PDF</span>
          )}
        </div>

        <p className="truncate text-[11px] text-secondary" title={displayName}>{displayName}</p>
        <p className="text-[10px] text-hint">{date}</p>

        {isPending && (
          <p className="text-[10px] text-hint">Analyse en cours…</p>
        )}
        {!isPending && !isError && (
          <p className="text-[10px] text-muted">
            {cv.match_count} match{cv.match_count !== 1 ? "s" : ""}
            {unseenCount > 0 && (
              <span className="ml-1 text-[9px] text-success">+{unseenCount}</span>
            )}
          </p>
        )}
      </div>

      {/* Delete controls */}
      <div
        className={cn(
          "flex flex-col items-center transition-opacity duration-150",
          showControls ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      >
        {/* Vertical wire from card bottom to trash row */}
        <div className="h-3.5 w-px bg-interactive-hover" />

        {/* Horizontal row: [cancel] ─ [trash] ─ [confirm] */}
        <div ref={rowRef} className="flex items-center">

          {/* Cancel button + wire to trash (left side) */}
          {deleteState === "confirm" && (
            <>
              <button
                aria-label="Annuler la suppression"
                onClick={() => setDeleteState("idle")}
                className="flex items-center justify-center rounded-md bg-interactive px-3 py-1.5 transition-colors hover:bg-interactive-hover active:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  width="14"
                  height="14"
                  className="text-primary"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              {/* Wire: right of cancel → left of trash */}
              <div className="h-px w-2 bg-interactive-hover" />
            </>
          )}

          {/* Trash button */}
          <button
            aria-label="Supprimer ce CV"
            disabled={deleteState === "confirm"}
            aria-disabled={deleteState === "confirm"}
            onClick={() => setDeleteState("confirm")}
            className={cn(
              "group flex h-7 w-7 items-center justify-center rounded-full border border-subtle bg-card transition-colors hover:border-transparent hover:bg-solid-destructive-hover active:bg-solid-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:cursor-not-allowed disabled:opacity-60",
              deleteState === "confirm" && "border-transparent bg-solid-destructive",
            )}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              width="14"
              height="14"
              className={cn(
                "transition-colors",
                deleteState === "confirm" ? "text-strong" : "text-muted group-hover:text-strong",
              )}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
              />
            </svg>
          </button>

          {/* Wire + confirm button (right side) */}
          {deleteState === "confirm" && (
            <>
              {/* Wire: right of trash → left of confirm */}
              <div className="h-px w-2 bg-interactive-hover" />
              <button
                aria-label="Confirmer la suppression"
                onClick={() => void handleConfirmDelete()}
                className="flex items-center justify-center rounded-md bg-solid-confirm px-3 py-1.5 transition-colors hover:bg-solid-confirm-hover active:bg-solid-confirm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-confirm"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  width="14"
                  height="14"
                  className="text-strong"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </button>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
