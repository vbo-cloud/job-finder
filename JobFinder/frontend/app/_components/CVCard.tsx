"use client";

import { cn } from "@/lib/utils";
import type { CVData } from "@/lib/api/types";

interface CVCardProps {
  cv: CVData;
}

export default function CVCard({ cv }: CVCardProps) {
  const isPending = cv.status === "pending" || cv.status === "processing";
  const isError   = cv.status === "error";
  const displayName = cv.name ?? "CV sans nom";
  const date = new Date(cv.uploaded_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="flex w-44 flex-shrink-0 flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-4">
      <div
        role={isPending ? "status" : undefined}
        aria-label={isPending ? "Analyse en cours" : undefined}
        className={cn(
          "flex aspect-[3/4] w-full items-center justify-center rounded-lg",
          isPending && "bg-white/[0.05]",
          !isPending && !isError && "bg-white/[0.08]",
          isError && "bg-red-500/[0.08]",
        )}
      >
        {isPending && (
          <svg className="h-5 w-5 animate-spin text-white/35" fill="none" viewBox="0 0 24 24" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z" />
          </svg>
        )}
        {isError && (
          <span className="text-xs text-red-400/60">Erreur</span>
        )}
        {!isPending && !isError && (
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
