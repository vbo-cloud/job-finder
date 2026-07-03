"use client";

import { useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import type { MatchOut } from "@/lib/api/types";
import MatchList from "./MatchList";
import { type MatchItemData } from "./MatchItem";

type SortKey = "score" | "salary" | "az";
type ContractFilter = "Tous" | "CDI" | "CDD";
const SCORE_THRESHOLDS = [60, 70, 80] as const;
type ScoreFilter = "Tous" | `${typeof SCORE_THRESHOLDS[number]}`;

function parseSalaryMax(salary: string | null): number {
  if (!salary) return 0;
  const digits = salary.replace(/\D/g, "");
  return digits ? parseInt(digits, 10) : 0;
}

function loadSeenIds(cvId: string): Set<string> {
  try {
    const raw = localStorage.getItem(`jf_seen_${cvId}`);
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
  } catch {
    return new Set();
  }
}

function persistSeenId(cvId: string, ids: Set<string>) {
  try {
    localStorage.setItem(`jf_seen_${cvId}`, JSON.stringify(Array.from(ids)));
  } catch { /* localStorage unavailable */ }
}


interface Props {
  cvId: string;
  matches: MatchOut[];
  loading: boolean;
  error: string | null;
}

export default function CorrespondancesPanel({ cvId, matches, loading, error }: Props) {
  const [tab, setTab]               = useState<"Matchs" | "Review">("Matchs");
  const [query, setQuery]           = useState("");
  const [sort, setSort]             = useState<SortKey>("score");
  const [contract, setContract]     = useState<ContractFilter>("Tous");
  const [minScore, setMinScore]     = useState<ScoreFilter>("Tous");
  const [filterOpen, setFilterOpen] = useState(false);
  const [filters, setFilters]       = useState({ nouvelle: true, vue: true });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saved, setSaved]           = useState(new Set<string>());
  const [applied, setApplied]       = useState(new Set<string>());
  const [rejected, setRejected]     = useState(new Set<string>());
  const [seenIds, setSeenIds] = useState<Set<string>>(() => loadSeenIds(cvId));
  const seenIdsRef = useRef(seenIds);
  seenIdsRef.current = seenIds; // sync ref on every render — read in useMemo without declaring as dep

  function toggleExpand(id: string) {
    const opening = selectedId !== id;
    setSelectedId(opening ? id : null);
    if (opening && !seenIds.has(id)) {
      setSeenIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        persistSeenId(cvId, next);
        return next;
      });
      apiClient.patch(`/cv/${cvId}/matches/${id}/seen`).catch((err: unknown) => {
        console.error("[jf] mark_match_seen failed:", err);
      });
    }
  }
  function toggleSaved(id: string) {
    setSaved((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const filtered = useMemo(() => {
    let arr = matches.filter((m) => !rejected.has(m.offer.id));
    const q = query.trim().toLowerCase();
    if (q) arr = arr.filter((m) =>
      `${m.offer.title} ${m.offer.company} ${m.offer.location}`.toLowerCase().includes(q),
    );
    if (contract !== "Tous") arr = arr.filter((m) => m.offer.contract_type === contract);
    if (minScore !== "Tous") arr = arr.filter((m) => Math.round(m.score * 100) >= +minScore);
    arr = arr.filter((m) => {
      const novel = m.is_new && !seenIdsRef.current.has(m.offer.id);
      return novel ? filters.nouvelle : filters.vue;
    });
    return [...arr].sort((a, b) =>
      sort === "az"     ? a.offer.title.localeCompare(b.offer.title, "fr") :
      sort === "salary" ? parseSalaryMax(b.offer.salary) - parseSalaryMax(a.offer.salary) :
      b.score - a.score,
    );
    // `applied` is not a filter criterion today — add it here if "hide applied" is introduced
    // seenIdsRef intentionally absent from deps — it's a ref, not reactive state
  }, [matches, rejected, query, contract, minScore, filters, sort]);

  const items: MatchItemData[] = filtered.map((m) => ({
    match:      m,
    isNew:      m.is_new && !seenIds.has(m.offer.id),
    isSaved:    saved.has(m.offer.id),
    isApplied:  applied.has(m.offer.id),
    isExpanded: selectedId === m.offer.id,
    onSelect:   () => toggleExpand(m.offer.id),
    onSave:     () => toggleSaved(m.offer.id),
    onApply:    () => setApplied((s) => new Set(s).add(m.offer.id)), // TODO: persist applied state to backend
    onReject:   () => {
      setRejected((s) => new Set(s).add(m.offer.id));
      if (selectedId === m.offer.id) setSelectedId(null);
    },
  }));

  const filterActive = !(filters.nouvelle && filters.vue);

  return (
    <section className="flex flex-1 flex-col overflow-hidden min-w-0">
      {/* Section header */}
      <div className="flex-none px-[22px] pt-[15px] pb-0 bg-surface border-b border-faint">
        <h2 className="m-0 font-bold text-[17px] text-strong whitespace-nowrap overflow-hidden text-ellipsis">
          Vos correspondances
        </h2>
        <p className="text-[12.5px] text-muted mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">
          {loading ? "Chargement…" : `${matches.length} correspondances analysées`}
        </p>
        <div className="flex items-center gap-[18px] mt-3.5">
          {(["Matchs", "Review"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "pb-2 -mb-px bg-transparent border-0 border-b-2 font-semibold text-[14px] cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                tab === t ? "border-strong text-strong" : "border-transparent text-hint hover:text-muted",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Filter bar */}
      {tab === "Matchs" && (
        <div className="flex-none flex items-center gap-[10px] px-[22px] py-[11px] bg-chip border-b border-faint flex-wrap">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] max-w-[320px] bg-page border border-soft rounded-[9px] px-3 py-2">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted shrink-0">
              <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
            </svg>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher un poste, une ville…"
              className="border-none outline-none bg-transparent text-[13px] text-strong placeholder:text-muted w-full"
            />
          </div>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="border border-soft rounded-[9px] px-2.5 py-2 text-[12.5px] text-body bg-page cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default">
            <option value="score">Trier : Pertinence</option>
            <option value="salary">Trier : Salaire</option>
            <option value="az">Trier : A → Z</option>
          </select>
          <select value={contract} onChange={(e) => setContract(e.target.value as ContractFilter)} className="border border-soft rounded-[9px] px-2.5 py-2 text-[12.5px] text-body bg-page cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default">
            <option value="Tous">Contrat : Tous</option>
            <option value="CDI">CDI</option>
            <option value="CDD">CDD</option>
          </select>
          <select value={minScore} onChange={(e) => setMinScore(e.target.value as ScoreFilter)} className="border border-soft rounded-[9px] px-2.5 py-2 text-[12.5px] text-body bg-page cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default">
            <option value="Tous">Score : Tous</option>
            {SCORE_THRESHOLDS.map((t) => (
              <option key={t} value={t}>Score ≥ {t} %</option>
            ))}
          </select>
          <div className="relative">
            <button
              onClick={() => setFilterOpen((o) => !o)}
              className={cn(
                "flex items-center gap-[7px] border rounded-[9px] px-[11px] py-2 text-[12.5px] text-body bg-page cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                filterOpen ? "border-default" : "border-soft",
              )}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 5h18l-7 8v6l-4-2v-6z" />
              </svg>
              Filtre
              {filterActive && <span className="h-1.5 w-1.5 rounded-full bg-new-offer" />}
            </button>
            {filterOpen && (
              <>
                <div onClick={() => setFilterOpen(false)} className="fixed inset-0 z-[29]" />
                <div className="absolute top-[calc(100%+6px)] left-0 z-30 bg-surface border border-faint rounded-xl shadow-[0_12px_32px_rgba(0,0,0,.13)] p-2 min-w-[196px]">
                  <p className="text-[10.5px] font-bold tracking-[.07em] uppercase text-muted px-2 pt-1.5 pb-2">Afficher</p>
                  {([
                    { key: "nouvelle" as const, label: "Nouvelles" },
                    { key: "vue" as const, label: "Vues" },
                  ]).map(({ key, label }) => (
                    <label key={key} className="flex items-center gap-[9px] px-2 py-2 rounded-[7px] text-[13px] text-body cursor-pointer hover:bg-overlay">
                      <input
                        type="checkbox"
                        checked={filters[key]}
                        onChange={() => setFilters((f) => ({ ...f, [key]: !f[key] }))}
                        className="h-[15px] w-[15px] cursor-pointer"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto px-[22px] py-4 pb-12">
        {tab === "Review" ? (
          <div className="text-center pt-20">
            <p className="font-bold text-[15px] text-muted">Rien à revoir pour l&apos;instant</p>
            <p className="text-[13px] text-hint mt-1.5">Les offres marquées « à revoir » apparaîtront ici.</p>
          </div>
        ) : error ? (
          <p className="text-xs text-destructive mt-8 text-center">{error} — impossible de charger les matchs</p>
        ) : !filters.nouvelle && !filters.vue ? (
          <p className="text-sm text-muted text-center mt-12">Tous les filtres sont désactivés — activez au moins un filtre.</p>
        ) : (
          <MatchList
            items={items}
            loading={loading}
            rejectedCount={rejected.size}
            onRestoreAll={() => setRejected(new Set())}
          />
        )}
      </div>
    </section>
  );
}
