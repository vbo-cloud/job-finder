"use client";

import { cn } from "@/lib/utils";
import type { MatchOut } from "@/lib/api/types";
import MatchAnalysisPanel from "./MatchAnalysisPanel";

export interface MatchItemData {
  match: MatchOut;
  isNew: boolean;
  isSaved: boolean;
  isApplied: boolean;
  isExpanded: boolean;
  /** True between the "Analyser cette offre" click and the polling resolution. */
  analysisPending: boolean;
  onSelect: () => void;
  onSave: () => void;
  onApply: () => void;
  onReject: () => void;
  onAnalyze: () => void;
}

const FT_OFFER_URL = "https://candidat.francetravail.fr/offres/recherche/detail";

function scoreTheme(pct: number): { color: string; barBg: string; golden: boolean } {
  if (pct > 90) return {
    color: "#a9791f",
    barBg: "linear-gradient(90deg,#d4af37,#f6d879)",
    golden: true,
  };
  const h = Math.round((pct / 100) * 132);
  const c = `hsl(${h} 60% 37%)`;
  return { color: c, barBg: c, golden: false };
}

function parseLocation(location: string): { city: string; dept: string } {
  const m = /^([^(]+)\s*\((\w+)\)/.exec(location);
  if (m) return { city: m[1].trim(), dept: m[2] };
  return { city: location, dept: "" };
}

function contractShort(title: string, contractType: string): string {
  const t = title.toLowerCase();
  if (t.includes("altern")) return "ALT";
  if (t.includes("stage") || t.includes("stagiaire")) return "STA";
  return contractType.slice(0, 3).toUpperCase();
}

function brandHue(name: string): number {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

// "use client" — runs in the browser only (one instance per page load), so a module-level cache is safe and never leaks between users.
const logoBadgeCache = new Map<string, { mono: string; bg: string; fg: string }>();

function logoBadge(company: string): { mono: string; bg: string; fg: string } {
  const key = company.trim();
  const cached = logoBadgeCache.get(key);
  if (cached) return cached;
  let result: { mono: string; bg: string; fg: string };
  if (key) {
    const words = key.split(/\s+/);
    const mono = (words.length > 1 ? words[0][0] + words[1][0] : key.slice(0, 2)).toUpperCase();
    result = { mono, bg: `hsl(${brandHue(key)} 38% 42%)`, fg: "#fff" };
  } else {
    result = { mono: "?", bg: "var(--bg-badge)", fg: "var(--text-muted)" };
  }
  logoBadgeCache.set(key, result);
  return result;
}

export default function MatchItem({
  match, isNew, isSaved, isApplied, isExpanded, analysisPending,
  onSelect, onSave, onApply, onReject, onAnalyze,
}: MatchItemData) {
  const { offer } = match;
  const pct = Math.round(match.score * 100);
  const { color, barBg, golden } = scoreTheme(pct);
  const { city, dept } = parseLocation(offer.location);
  const meta = [city, dept, offer.contract_type].filter(Boolean).join(" · ");
  const badge = logoBadge(offer.company || "");
  const short = contractShort(offer.title, offer.contract_type);

  return (
    <div
      className={cn(
        "relative rounded-[13px] overflow-hidden border transition-[border-color,box-shadow] duration-150",
        isExpanded
          ? "shadow-[0_6px_22px_rgba(0,0,0,.10)] border-match bg-page"
          : "bg-page border-faint",
      )}
    >
      {/* Bookmark — absolute top-right, above the clickable row */}
      <button
        onClick={(e) => { e.stopPropagation(); onSave(); }}
        aria-label={isSaved ? "Retirer des favoris" : "Sauvegarder"}
        className={cn(
          "absolute top-3 right-3.5 z-10 flex h-8 w-8 items-center justify-center rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
          isSaved ? "border-match bg-match-skill text-match-skill" : "border-faint bg-page text-muted hover:border-subtle",
        )}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill={isSaved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        </svg>
      </button>

      {/* Clickable header row */}
      <div
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); } }}
        className="flex items-stretch cursor-pointer hover:bg-overlay rounded-[13px] transition-colors"
      >
        {/* Score column */}
        <div className="relative flex flex-none w-[70px] flex-col items-center justify-center gap-2 py-4 px-2 bg-chip border-r border-faint">
          <span className="absolute top-3 left-0 right-0 text-center text-[10.5px] font-bold tracking-[.05em] text-muted">
            {short}
          </span>
          {golden ? (
            <span
              className="font-mono text-[20px] font-bold tabular-nums"
              style={{
                background: "linear-gradient(95deg,#b8860b,#f6d879,#fff3c4,#f6d879,#b8860b)",
                backgroundSize: "200% 100%",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
                animation: "shine 2.5s linear infinite",
              }}
            >
              {pct}%
            </span>
          ) : (
            <span className="font-mono text-[20px] font-bold tabular-nums" style={{ color }}>
              {pct}%
            </span>
          )}
          <div className="h-[5px] w-11 rounded-full bg-interactive overflow-hidden">
            <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: barBg }} />
          </div>
        </div>

        {/* Content column */}
        <div className="flex flex-1 min-w-0 flex-col gap-[9px] py-4 px-[18px]">
          <div className="flex items-center gap-3">
            <div
              className="flex flex-none h-[42px] w-[42px] items-center justify-center rounded-xl text-sm font-bold"
              style={{ background: badge.bg, color: badge.fg }}
            >
              {badge.mono}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <a
                  href={`${FT_OFFER_URL}/${offer.ft_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="font-bold text-[15px] text-strong leading-tight hover:text-accent transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default rounded"
                >
                  {offer.title}
                </a>
                {isNew && (
                  <span className="text-[10.5px] font-bold px-2 py-0.5 rounded-full bg-new-offer text-new-offer tracking-[.02em]">
                    Nouveau
                  </span>
                )}
              </div>
              <p className="text-[12.5px] font-medium text-muted mt-0.5">
                {offer.company || "Entreprise non précisée"}
              </p>
            </div>
          </div>

          <p className="text-[12.5px] text-secondary">{meta}</p>

          {(match.analysis?.matched_skills.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {match.analysis!.matched_skills.slice(0, 3).map((s) => (
                <span key={s} className="inline-flex items-center gap-[5px] text-[11.5px] font-semibold px-[9px] py-1 rounded-[6px] bg-match-skill text-match-skill">
                  <span className="font-bold">✓</span>{s}
                </span>
              ))}
            </div>
          )}

          {offer.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {offer.skills.slice(0, 5).map((s) => (
                <span key={s} className="text-[11.5px] font-medium px-[9px] py-1 rounded-[6px] bg-overlay text-muted">
                  {s}
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-[7px] text-[12px] text-muted leading-snug">
            <span className="text-hint">—</span>
            {match.analysis?.status === "done" && match.analysis.synthese ? (
              <span>{match.analysis.synthese}</span>
            ) : (
              <span>Analyse IA — dépliez l&apos;offre pour la lancer.</span>
            )}
          </div>
        </div>

        {/* Chevron */}
        <div className="flex flex-none items-center justify-center px-3.5 self-center">
          <span className={cn("flex h-8 w-8 items-center justify-center text-muted transition-transform duration-200", isExpanded && "rotate-180")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </div>
      </div>

      {/* Accordion panel */}
      {isExpanded && (
        <div className="border-t border-faint px-5 py-5 grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-5 [animation:expandIn_.2s_ease]">
          {/* Offer column */}
          <div>
            <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-3">Descriptif de l&apos;offre</p>
            <div className="flex items-center gap-2 text-sm font-semibold text-strong">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-success shrink-0">
                <path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
              {offer.salary ?? "Salaire non communiqué"}
            </div>
            {offer.rome_code && (
              <div className="mt-3">
                <span className="inline-flex px-2.5 py-1 rounded-[7px] bg-accent-muted text-accent text-[12px] font-semibold">
                  {offer.rome_code}
                </span>
              </div>
            )}
            <div className="flex flex-col gap-[9px] mt-3.5 text-[13px] text-body leading-relaxed">
              <div className="flex gap-[9px]">
                <span className="text-success flex-none pt-px">•</span>
                <span>Poste en {offer.contract_type}, basé à {city}{dept ? ` (${dept})` : ""}.</span>
              </div>
              {offer.skills.length > 0 && (
                <div className="flex gap-[9px]">
                  <span className="text-success flex-none pt-px">•</span>
                  <span>Compétences requises : {offer.skills.slice(0, 3).join(", ")}.</span>
                </div>
              )}
            </div>
            {offer.description && (
              <p className="mt-4 text-[12.5px] text-body leading-relaxed whitespace-pre-line">
                {offer.description}
              </p>
            )}
            <div className="flex gap-2 mt-[18px] flex-wrap">
              <button
                onClick={onApply}
                disabled={isApplied}
                className={cn(
                  "flex-1 min-w-[130px] px-4 py-3 rounded-[10px] font-semibold text-[13.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-confirm",
                  isApplied
                    ? "border border-match bg-match-skill text-match-skill cursor-default"
                    : "bg-solid-confirm text-on-solid hover:bg-solid-confirm-hover cursor-pointer",
                )}
              >
                {isApplied ? "Candidature envoyée ✓" : "Postuler"}
              </button>
              <button
                onClick={onSave}
                className={cn(
                  "px-4 py-3 rounded-[10px] font-semibold text-[13.5px] border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                  isSaved
                    ? "border-match bg-match-skill text-match-skill"
                    : "border-soft bg-page text-strong hover:border-default",
                )}
              >
                {isSaved ? "Sauvegardée ✓" : "Sauvegarder"}
              </button>
              <button
                onClick={onReject}
                className="px-4 py-3 rounded-[10px] font-semibold text-[13.5px] border border-soft bg-page text-muted transition-colors hover:border-destructive hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
              >
                Rejeter
              </button>
            </div>
          </div>

          {/* Agent review column */}
          <MatchAnalysisPanel
            analysis={match.analysis}
            analysisPending={analysisPending}
            onAnalyze={onAnalyze}
            offerSkills={offer.skills}
          />
        </div>
      )}
    </div>
  );
}
