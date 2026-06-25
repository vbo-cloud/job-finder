"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import type { CVData } from "@/lib/api/types";

interface CVCardProps {
  cv: CVData;
}

export default function CVCard({ cv }: CVCardProps) {
  const isPending   = cv.status === "pending" || cv.status === "processing";
  const isError     = cv.status === "error";
  const displayName = cv.name ?? "CV sans nom";
  const date = new Date(cv.uploaded_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const [thumbnailSrc, setThumbnailSrc] = useState<string | null>(null);

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

  return (
    <div className="flex w-44 flex-shrink-0 flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-4">
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
    </div>
  );
}
