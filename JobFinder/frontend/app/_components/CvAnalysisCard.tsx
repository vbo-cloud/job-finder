"use client";

import { useEffect, useRef, useState } from "react";
import posthog from "posthog-js";
import apiClient from "@/lib/api/client";
import type { CvAnalysisOut } from "@/lib/api/types";
import AnalysisPointsList from "./AnalysisPointsList";

const POLL_INTERVAL_MS = 3000;

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
  const hasTrackedViewedRef = useRef(false);

  useEffect(() => {
    if (analysis?.status === "done" && !hasTrackedViewedRef.current) {
      hasTrackedViewedRef.current = true;
      posthog.capture("cv_analysis_viewed", { ats_score: analysis.ats_score, cv_id: cvId });
    }
  }, [analysis, cvId]);

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
  }, [cvId]);

  return (
    // The frame (border/bg) is owned by the accordion wrapper in
    // CVDetailSection.tsx — this component only pads its content.
    <div className="w-full p-3.5 md:p-[18px]">
      {fetchFailed ? (
        <p className="text-[13px] text-muted">Analyse indisponible pour ce CV</p>
      ) : analysis?.status === "error" ? (
        <p className="text-[13px] text-destructive leading-relaxed">
          L&apos;analyse de votre CV a échoué. Elle sera relancée automatiquement si vous
          modifiez votre expérience ou votre recherche dans votre profil.
        </p>
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
          {analysis.synthese && (
            <div>
              <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-2">
                Synthèse
              </p>
              <p className="text-[13px] text-body leading-relaxed">{analysis.synthese}</p>
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
