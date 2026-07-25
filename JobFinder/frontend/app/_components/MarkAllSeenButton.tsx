"use client";

import { useState } from "react";
import apiClient from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface Props {
  cvId: string;
  disabled?: boolean;
  /** Called after a successful mark-all-seen PATCH so the parent can clear the
   * "Nouveau" badges locally and refresh the library's unseen_count badge.
   * Deliberately fired only once the server confirms, unlike the per-offer
   * mark-seen in CorrespondancesPanel (toggleExpand), which updates local
   * state optimistically before the PATCH resolves — a bulk action failing
   * silently local-only would be harder to notice/retry than a single one. */
  onMarkedAllSeen: () => void;
}

export default function MarkAllSeenButton({ cvId, disabled, onMarkedAllSeen }: Props) {
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  function handleClick() {
    setLoading(true);
    setFailed(false);
    apiClient
      .patch(`/cv/${cvId}/mark-all-seen`)
      .then(() => onMarkedAllSeen())
      .catch((err: unknown) => {
        console.error("[jf] mark_all_seen failed:", err);
        setFailed(true);
      })
      .finally(() => setLoading(false));
  }

  return (
    // ml-auto pushes this flush right — only works because the caller
    // (CorrespondancesPanel's filter bar) renders it inside a flex row.
    <div className="ml-auto flex items-center gap-2">
      {/* Suppressed once nothing is left to mark (e.g. cleared from another tab) —
       * a stale failure message about a mark-all attempt no longer applies. */}
      {failed && !disabled && <span className="text-[12px] text-destructive">Échec — réessayez</span>}
      <button
        onClick={handleClick}
        disabled={disabled || loading}
        className={cn(
          "text-[12.5px] font-semibold text-body underline hover:text-strong transition-colors",
          "disabled:cursor-default disabled:text-muted disabled:no-underline",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default rounded",
        )}
      >
        {loading ? "Marquage…" : "Marquer tout comme vu"}
      </button>
    </div>
  );
}
