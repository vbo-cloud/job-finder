"use client";

import { useState } from "react";
import apiClient from "@/lib/api/client";

const BUTTON_CLASS =
  "px-3 py-2 rounded-[10px] font-semibold text-[12.5px] border border-soft bg-page text-strong " +
  "hover:border-default transition-colors cursor-pointer " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default " +
  "disabled:cursor-default disabled:text-muted disabled:hover:border-soft";

interface Props {
  cvId: string;
  /** Called after a successful retry POST — the parent should refetch the CV list so
   * rome_reanalysis_available flips back to false once cvs.rome_analyzed_at updates. */
  onReanalyzed: () => void;
}

export default function RomeReanalysisButton({ cvId, onReanalyzed }: Props) {
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(false);
  const [hovered, setHovered] = useState(false);

  function handleClick() {
    setRetrying(true);
    setRetryError(false);
    apiClient
      .post(`/cv/${cvId}/rome/retry`)
      .then(() => onReanalyzed())
      .catch((err: unknown) => {
        console.error("[jf] cv rome reanalysis failed:", err);
        setRetryError(true);
      })
      .finally(() => setRetrying(false));
  }

  return (
    <div className="flex flex-col items-start gap-1.5">
      <span
        className="relative inline-flex"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <button onClick={handleClick} disabled={retrying} className={BUTTON_CLASS}>
          {retrying ? "Analyse…" : "Mettre à jour les métiers détectés"}
        </button>
        {hovered && (
          <span
            role="tooltip"
            className="absolute bottom-full left-1/2 z-10 mb-1.5 w-64 -translate-x-1/2 rounded border border-default bg-surface px-2.5 py-1.5 text-xs text-body shadow-lg"
          >
            Votre description de recherche a changé depuis la dernière analyse de ce CV — les
            métiers détectés (et les offres associées) ont peut-être besoin d&apos;être mis à jour.
          </span>
        )}
      </span>
      {retryError && (
        <p className="text-[12px] text-destructive">La mise à jour a échoué — réessayez.</p>
      )}
    </div>
  );
}
