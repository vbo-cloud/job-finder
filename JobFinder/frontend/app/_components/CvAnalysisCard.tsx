"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/api/client";
import type { CvAnalysisOut } from "@/lib/api/types";
import AnalysisPointsList from "./AnalysisPointsList";

const POLL_INTERVAL_MS = 3000;

const RETRY_BUTTON_CLASS =
  "px-4 py-3 rounded-[10px] font-semibold text-[13.5px] border border-soft bg-page text-strong " +
  "hover:border-default transition-colors cursor-pointer " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default " +
  "disabled:cursor-default disabled:text-muted disabled:hover:border-soft";

// Same hue ramp as scoreTheme() in MatchItem.tsx, without the golden tier —
// kept local until a third caller makes a shared utility worthwhile.
// TODO(share): extract alongside scoreTheme() if MatchItem.tsx gets refactored.
function atsScoreColor(pct: number): string {
  const h = Math.round((pct / 100) * 132);
  return `hsl(${h} 60% 37%)`;
}

interface Props {
  cvId: string;
}

export default function CvAnalysisCard({ cvId }: Props) {
  const [analysis, setAnalysis] = useState<CvAnalysisOut | null>(null);
  const [fetchFailed, setFetchFailed] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(false);
  // Bumped after a successful retry POST to re-enter the polling effect
  // immediately instead of waiting for the next natural fetch.
  const [pollGeneration, setPollGeneration] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const fetchAnalysis = () => {
      apiClient
        .get<CvAnalysisOut>(`/cv/${cvId}/analysis`)
        .then((res) => {
          if (cancelled) return;
          setAnalysis(res.data);
          setFetchFailed(false);
          // The agent writes pending → processing → done/error; keep polling
          // until a terminal status so the card fills in without a reload.
          if (res.data.status === "pending" || res.data.status === "processing") {
            timer = setTimeout(fetchAnalysis, POLL_INTERVAL_MS);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          // Silent error state — this card is secondary to the matches list.
          console.error("[jf] cv analysis fetch failed:", err);
          setFetchFailed(true);
        });
    };
    fetchAnalysis();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [cvId, pollGeneration]);

  function handleRetry() {
    setRetrying(true);
    setRetryError(false);
    apiClient
      .post(`/cv/${cvId}/analysis/retry`)
      .then(() => {
        // Optimistic: reflect "processing" immediately and restart the
        // polling effect rather than waiting up to POLL_INTERVAL_MS.
        setAnalysis((prev) => (prev ? { ...prev, status: "processing" } : prev));
        setPollGeneration((n) => n + 1);
      })
      .catch((err: unknown) => {
        console.error("[jf] cv analysis retry failed:", err);
        setRetryError(true);
      })
      .finally(() => setRetrying(false));
  }

  return (
    <div className="w-full rounded-xl border border-faint bg-chip p-[18px]">
      <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-3">
        Analyse de votre CV
      </p>

      {fetchFailed ? (
        <p className="text-[13px] text-muted">Analyse indisponible pour ce CV</p>
      ) : analysis?.status === "error" ? (
        <div className="flex flex-col gap-3 items-start">
          <p className="text-[13px] text-destructive leading-relaxed">
            L&apos;analyse de votre CV a échoué — vous pouvez la relancer.
          </p>
          <button onClick={handleRetry} disabled={retrying} className={RETRY_BUTTON_CLASS}>
            {retrying ? "Relance…" : "Relancer l'analyse"}
          </button>
          {retryError && (
            <p className="text-[12px] text-destructive">La relance a échoué — réessayez.</p>
          )}
        </div>
      ) : !analysis || analysis.status === "pending" || analysis.status === "processing" ? (
        <p className="text-[13px] text-muted">Analyse de votre CV en cours…</p>
      ) : (
        <div className="flex flex-col gap-4">
          {analysis.ats_score !== null && (
            <div className="flex items-center gap-3">
              <span
                className="font-mono text-[24px] font-bold tabular-nums"
                style={{ color: atsScoreColor(analysis.ats_score) }}
              >
                {analysis.ats_score}
              </span>
              <div className="flex-1">
                <p className="text-[12px] font-semibold text-strong">Score ATS</p>
                <div className="h-[5px] w-full rounded-full bg-interactive overflow-hidden mt-1">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${analysis.ats_score}%`,
                      background: atsScoreColor(analysis.ats_score),
                    }}
                  />
                </div>
              </div>
            </div>
          )}
          <AnalysisPointsList title="Points forts" items={analysis.points_forts} variant="positive" />
          <AnalysisPointsList title="Points faibles" items={analysis.points_faibles} variant="negative" />
          <AnalysisPointsList title="Suggestions" items={analysis.suggestions} variant="suggestion" />
          {analysis.coherence_intention && (
            <div>
              <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-2">
                Cohérence avec votre recherche
              </p>
              <p className="text-[13px] text-body leading-relaxed">{analysis.coherence_intention}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
