"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { MatchOut } from "@/lib/api/types";

interface Props { match: MatchOut; }

export default function MatchItem({ match }: Props) {
  const [open, setOpen] = useState(false);
  const scorePercent = Math.round(match.score * 100);

  return (
    <div className="rounded-xl border border-faint bg-chip overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-chip transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        {/* Score badge */}
        <span className={cn(
          "text-[11px] font-medium tabular-nums w-10 shrink-0",
          scorePercent >= 75
            ? "text-success"
            : scorePercent >= 50
              ? "text-warning"
              : "text-muted",
        )}>
          {scorePercent}%
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-[12px] text-body truncate">{match.offer.title}</p>
          <p className="text-[10px] text-muted truncate">
            {match.offer.company} · {match.offer.location} · {match.offer.contract_type}
          </p>
        </div>

        <svg
          xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.5" width="12" height="12"
          className={cn("shrink-0 text-label transition-transform", open && "rotate-180")}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-faint flex flex-col gap-2">
          {match.offer.salary && (
            <p className="text-[10px] text-muted">Salaire : {match.offer.salary}</p>
          )}
          {match.offer.rome_code && (
            <p className="text-[10px] text-hint">Code ROME : {match.offer.rome_code}</p>
          )}
          {match.offer.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {match.offer.skills.map((skill) => (
                <span
                  key={skill}
                  className="text-[9px] px-2 py-0.5 rounded-full bg-overlay text-muted"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
          <p className="text-[10px] text-empty mt-2 italic">
            Review IA spécifique — bientôt disponible
          </p>
        </div>
      )}
    </div>
  );
}
