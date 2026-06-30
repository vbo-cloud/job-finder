"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { getRomeLabel } from "@/lib/rome-codes";
import type { MatchOut } from "@/lib/api/types";

const FT_OFFER_URL = "https://candidat.francetravail.fr/offres/recherche/detail";

type Tab = "offre" | "analyse";

interface Props { match: MatchOut; }

export default function MatchItem({ match }: Props) {
  const [open, setOpen]           = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("offre");
  const scorePercent = Math.round(match.score * 100);

  const expired = match.offer.expires_at !== null && new Date(match.offer.expires_at) < new Date();
  const offerUrl = `${FT_OFFER_URL}/${match.offer.ft_id}`;

  return (
    <div className="rounded-xl border border-faint bg-chip overflow-hidden">
      {/* Row — score | title + meta | expand toggle */}
      <div className="flex items-center gap-4 px-4 py-3">
        <span className={cn(
          "text-[11px] font-medium tabular-nums w-10 shrink-0",
          scorePercent >= 75 ? "text-success" : scorePercent >= 50 ? "text-warning" : "text-muted",
        )}>
          {scorePercent}%
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            {expired ? (
              <span className="text-[12px] text-muted truncate">{match.offer.title}</span>
            ) : (
              <a
                href={offerUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[12px] text-body hover:text-accent active:text-strong transition-colors truncate focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default rounded"
              >
                {match.offer.title}
              </a>
            )}
            {expired && (
              <span className="shrink-0 text-[8px] px-1.5 py-0.5 rounded-full bg-destructive-muted text-destructive border border-destructive/20">
                Expirée
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted truncate">
            {match.offer.company} · {match.offer.location} · {match.offer.contract_type}
          </p>
        </div>

        <button
          onClick={() => setOpen((o) => !o)}
          aria-label={open ? "Réduire" : "Développer"}
          className="shrink-0 p-1 text-label hover:text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default rounded"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="1.5" width="12" height="12"
            className={cn("transition-transform", open && "rotate-180")}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
      </div>

      {open && (
        <div className="border-t border-faint">
          {/* Tab header */}
          <div className="flex gap-5 px-4 pt-3 pb-0 border-b border-faint">
            {(["offre", "analyse"] as Tab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  "pb-2 text-[10px] tracking-wide transition-colors capitalize border-b-2 -mb-px focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default",
                  activeTab === tab
                    ? "text-primary border-active"
                    : "text-hint border-transparent hover:text-muted",
                )}
              >
                {tab === "offre" ? "Offre" : "Analyse"}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="px-4 py-3 flex flex-col gap-2">
            {activeTab === "offre" && (
              <>
                {match.offer.rome_code && (
                  <span className="self-start text-[9px] px-2 py-0.5 rounded-full bg-accent-muted border border-accent text-accent">
                    {getRomeLabel(match.offer.rome_code)}
                  </span>
                )}
                {match.offer.salary && (
                  <p className="text-[10px] text-muted">Salaire : {match.offer.salary}</p>
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
              </>
            )}

            {activeTab === "analyse" && (
              <p className="text-[10px] text-empty italic mt-1">
                Analyse IA spécifique — bientôt disponible
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
