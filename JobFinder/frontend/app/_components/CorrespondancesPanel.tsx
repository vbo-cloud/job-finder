"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import type { CVMatchesOut, MatchAnalysisOut, MatchOut } from "@/lib/api/types";
import { notifyCreditsConsumed } from "@/lib/creditsBus";
import MatchList from "./MatchList";
import PaginationBar from "./PaginationBar";
import { type MatchItemData } from "./MatchItem";

const ANALYSIS_POLL_INTERVAL_MS = 3000;
const PAGE_SIZE = 20;

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
  /** Called once a match is confirmed marked seen server-side, so the parent
   * can refresh the library's unseen_count badge for this CV. */
  onMatchSeen?: () => void;
}

export default function CorrespondancesPanel({ cvId, matches, loading, error, onMatchSeen }: Props) {
  const [tab, setTab]               = useState<"Offres" | "Sauvegardées">("Offres");
  const [query, setQuery]           = useState("");
  const [filters, setFilters]       = useState({ nouvelle: true, vue: true });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage]             = useState(1);
  const [savedPage, setSavedPage]   = useState(1);
  const contentRef = useRef<HTMLDivElement>(null);
  const [saved, setSaved]           = useState(new Set<string>());
  const [rejected, setRejected]     = useState(new Set<string>());
  const [seenIds, setSeenIds] = useState<Set<string>>(() => loadSeenIds(cvId));
  const seenIdsRef = useRef(seenIds);
  seenIdsRef.current = seenIds; // sync ref on every render — read in useMemo without declaring as dep
  // Offer IDs whose pair analysis was manually triggered and is still being polled.
  // Sets are reference-equal when mutated in place, so every update below builds
  // a new Set (new Set(prev) / Array.from(prev).filter(...)) rather than mutating
  // prev directly — mutating it would leave the useEffect/useMemo deps unaware
  // a change happened.
  const [analysisPending, setAnalysisPending] = useState(new Set<string>());
  // Fresher analyses fetched by the polling — supersede the `matches` prop until
  // the parent refetches (the prop only refreshes on CV/zone change).
  const [analysisOverrides, setAnalysisOverrides] = useState(new Map<string, MatchAnalysisOut>());
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    if (analysisPending.size === 0) return;
    const timer = setInterval(() => {
      apiClient
        .get<CVMatchesOut>(`/matches/cv/${cvId}`)
        .then((res) => {
          const byOffer = new Map(res.data.matches.map((m) => [m.offer.id, m.analysis]));
          setAnalysisOverrides((prev) => {
            const next = new Map(prev);
            analysisPending.forEach((id) => {
              const analysis = byOffer.get(id);
              if (analysis) next.set(id, analysis);
            });
            return next;
          });
          setAnalysisPending((prev) => {
            const next = new Set(
              Array.from(prev).filter((id) => {
                const analysis = byOffer.get(id);
                return !(analysis && (analysis.status === "done" || analysis.status === "error"));
              }),
            );
            return next.size === prev.size ? prev : next;
          });
        })
        .catch((err: unknown) => {
          console.error("[jf] analysis polling failed:", err);
        });
    }, ANALYSIS_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [
    // analysisPending as a dep means the interval restarts on every tick where
    // at least one offer resolves (new Set reference) — the remaining pending
    // offers can wait up to one extra ANALYSIS_POLL_INTERVAL_MS as a result.
    // Acceptable at today's scale; revisit if concurrent analyses grow.
    analysisPending,
    cvId,
  ]);

  function requestAnalysis(offerId: string) {
    setAnalysisError(null);
    apiClient
      .post(`/matches/${cvId}/offers/${offerId}/analyze`)
      .then(() => {
        setAnalysisPending((prev) => new Set(prev).add(offerId));
        notifyCreditsConsumed();
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        console.error("[jf] match analysis request failed:", err);
        setAnalysisError(
          status === 402
            ? "Crédits d'analyse épuisés"
            : "Impossible de lancer l'analyse — réessayez plus tard",
        );
      });
  }

  useEffect(() => {
    // Backend still reports is_new: true for an offer the local cache thinks
    // is already handled — a previous mark-seen PATCH silently failed (e.g.
    // the CORS misconfiguration fixed alongside this). Retry it so the
    // library badge eventually reflects reality instead of staying wrong
    // forever — the backend, not localStorage, decides when to stop retrying.
    for (const m of matches) {
      if (!m.is_new || !seenIdsRef.current.has(m.offer.id)) continue;
      apiClient
        .patch(`/cv/${cvId}/matches/${m.offer.id}/seen`)
        .then(() => onMatchSeen?.())
        .catch((err: unknown) => {
          console.error("[jf] retry mark_match_seen failed:", err);
        });
    }
  }, [matches, cvId, onMatchSeen]);

  function toggleExpand(id: string) {
    const opening = selectedId !== id;
    setSelectedId(opening ? id : null);
    setAnalysisError(null);
    if (opening && !seenIds.has(id)) {
      setSeenIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        persistSeenId(cvId, next);
        return next;
      });
      apiClient
        .patch(`/cv/${cvId}/matches/${id}/seen`)
        .then(() => onMatchSeen?.())
        .catch((err: unknown) => {
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
      `${m.offer.title} ${m.offer.company} ${m.offer.location} ${m.offer.description ?? ""}`.toLowerCase().includes(q),
    );
    arr = arr.filter((m) => {
      const novel = m.is_new && !seenIdsRef.current.has(m.offer.id);
      return novel ? filters.nouvelle : filters.vue;
    });
    return [...arr].sort((a, b) => b.score - a.score);
    // seenIdsRef intentionally absent from deps — it's a ref, not reactive state
  }, [matches, rejected, query, filters]);

  // Back to page 1 whenever the visible set is redefined by the user
  useEffect(() => {
    setPage(1);
  }, [query, filters, cvId]);

  useEffect(() => {
    setSavedPage(1);
  }, [cvId]);

  // Clamp instead of resetting when `filtered` shrinks in place (e.g. an offer
  // rejected on the last page) so the user stays as close as possible to where
  // they were.
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paginated = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  function goToPage(p: number) {
    setPage(p);
    contentRef.current?.scrollTo({ top: 0 });
  }

  function goToSavedPage(p: number) {
    setSavedPage(p);
    contentRef.current?.scrollTo({ top: 0 });
  }

  function toItemData(m: MatchOut, searchQuery?: string): MatchItemData {
    const override = analysisOverrides.get(m.offer.id);
    return {
      match:      override ? { ...m, analysis: override } : m,
      isNew:      m.is_new && !seenIds.has(m.offer.id),
      isSaved:    saved.has(m.offer.id),
      isExpanded: selectedId === m.offer.id,
      analysisPending: analysisPending.has(m.offer.id),
      analysisError: selectedId === m.offer.id ? analysisError : null,
      searchQuery,
      onSelect:   () => toggleExpand(m.offer.id),
      onSave:     () => toggleSaved(m.offer.id),
      onReject:   () => {
        setRejected((s) => new Set(s).add(m.offer.id));
        if (selectedId === m.offer.id) setSelectedId(null);
      },
      onAnalyze:  () => requestAnalysis(m.offer.id),
    };
  }

  const items: MatchItemData[] = paginated.map((m) => toItemData(m, query));

  // The Sauvegardées list is built from the full `matches` set (minus rejected
  // offers), independent of the Offres tab's query/Nouvelles-Vues filters — a
  // saved offer stays visible here no matter how the Offres tab is currently
  // narrowed. It has its own pagination, separate from the Offres one.
  const savedMatches = matches.filter((m) => !rejected.has(m.offer.id) && saved.has(m.offer.id));
  const savedTotalPages = Math.max(1, Math.ceil(savedMatches.length / PAGE_SIZE));
  const savedCurrentPage = Math.min(savedPage, savedTotalPages);
  const savedItems: MatchItemData[] = savedMatches
    .slice((savedCurrentPage - 1) * PAGE_SIZE, savedCurrentPage * PAGE_SIZE)
    .map((m) => toItemData(m));

  const displayedItems = tab === "Sauvegardées" ? savedItems : items;

  // Each tab drives its own PaginationBar (rendered above and below the list)
  const pagination = tab === "Sauvegardées"
    ? { page: savedCurrentPage, totalPages: savedTotalPages, onPageChange: goToSavedPage }
    : { page: currentPage, totalPages, onPageChange: goToPage };

  return (
    <section className="flex flex-1 flex-col overflow-hidden min-w-0">
      {/* Section header */}
      <div className="flex-none px-[22px] pt-[15px] pb-0 bg-surface border-b border-faint">
        <h2 className="m-0 font-bold text-[17px] text-strong whitespace-nowrap overflow-hidden text-ellipsis">
          Vos correspondances
        </h2>
        <p className="text-[12.5px] text-muted mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">
          {loading
            ? "Chargement…"
            : tab === "Sauvegardées"
            ? `${savedMatches.length} offre${savedMatches.length > 1 ? "s" : ""} sauvegardée${savedMatches.length > 1 ? "s" : ""}`
            : `${matches.length} correspondances analysées`}
        </p>
        <div className="flex items-center gap-[18px] mt-3.5">
          {(["Offres", "Sauvegardées"] as const).map((t) => (
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
      {tab === "Offres" && (
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
          <div className="flex items-center gap-[10px] border border-soft rounded-[9px] px-3 py-2 bg-page">
            <span className="text-[10.5px] font-bold tracking-[.07em] uppercase text-muted">Offres</span>
            {([
              { key: "nouvelle" as const, label: "Nouvelles" },
              { key: "vue" as const, label: "Vues" },
            ]).map(({ key, label }) => (
              <label key={key} className="flex items-center gap-[7px] text-[12.5px] text-body cursor-pointer mr-[6px] last:mr-0">
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
        </div>
      )}

      {/* Content area */}
      <div ref={contentRef} className="flex-1 overflow-y-auto px-[22px] py-4 pb-12">
        {error ? (
          <p className="text-xs text-destructive mt-8 text-center">{error} — impossible de charger les matchs</p>
        ) : tab === "Offres" && !filters.nouvelle && !filters.vue ? (
          <p className="text-sm text-muted text-center mt-12">Tous les filtres sont désactivés — activez au moins un filtre.</p>
        ) : (
          <>
            {!loading && <PaginationBar {...pagination} className="mb-4" />}
            <MatchList
              items={displayedItems}
              loading={loading}
              rejectedCount={rejected.size}
              onRestoreAll={() => setRejected(new Set())}
            />
            {!loading && <PaginationBar {...pagination} className="mt-5" />}
          </>
        )}
      </div>
    </section>
  );
}
