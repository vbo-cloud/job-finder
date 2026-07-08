"use client";

import type { MatchAnalysisOut } from "@/lib/api/types";
import AnalysisPointsList from "./AnalysisPointsList";

interface Props {
  analysis: MatchAnalysisOut | null;
  analysisPending: boolean;
  onAnalyze: () => void;
  offerSkills: string[];
}

const ANALYZE_BUTTON_CLASS =
  "px-4 py-3 rounded-[10px] font-semibold text-[13.5px] border border-soft bg-page text-strong " +
  "hover:border-default transition-colors cursor-pointer " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default " +
  "disabled:cursor-default disabled:text-muted disabled:hover:border-soft";

/** "Review de l'agent" column of an expanded MatchItem — pair analysis states + offer skills. */
export default function MatchAnalysisPanel({ analysis, analysisPending, onAnalyze, offerSkills }: Props) {
  const inProgress = analysisPending || analysis?.status === "processing";

  return (
    <div className="rounded-xl border border-faint bg-chip p-[18px]">
      <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-3.5">
        Review de l&apos;agent
      </p>

      {inProgress ? (
        <button disabled className={ANALYZE_BUTTON_CLASS}>
          Analyse en cours…
        </button>
      ) : analysis?.status === "done" ? (
        <div className="flex flex-col gap-4">
          {analysis.synthese && (
            <p className="text-[13.5px] font-semibold text-strong leading-relaxed p-3 bg-card border border-faint rounded-[10px]">
              {analysis.synthese}
            </p>
          )}
          <AnalysisPointsList title="Points forts" items={analysis.points_forts} variant="positive" />
          <AnalysisPointsList
            title="Points d'amélioration"
            items={analysis.points_amelioration.map((p) =>
              p.suggestion_concrete ? `${p.constat} — ${p.suggestion_concrete}` : p.constat
            )}
            variant="negative"
          />
        </div>
      ) : analysis?.status === "error" ? (
        <div className="flex flex-col gap-3 items-start">
          <p className="text-[13px] text-destructive leading-relaxed">
            L&apos;analyse a échoué — vous pouvez la relancer.
          </p>
          <button onClick={onAnalyze} className={ANALYZE_BUTTON_CLASS}>
            Analyser cette offre (consomme 1 crédit)
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3 items-start">
          <p className="text-[13px] text-body leading-relaxed">
            Obtenez une analyse détaillée de votre CV face à cette offre : compétences
            correspondantes, points forts et pistes d&apos;amélioration.
          </p>
          <button onClick={onAnalyze} className={ANALYZE_BUTTON_CLASS}>
            Analyser cette offre avec l&apos;IA
          </button>
        </div>
      )}

      {offerSkills.length > 0 && (
        <>
          <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mt-[18px] mb-2.5">
            Compétences détectées
          </p>
          <div className="flex flex-wrap gap-[7px]">
            {offerSkills.slice(0, 5).map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-[5px] px-[10px] py-[5px] rounded-[7px] bg-match-skill text-match-skill text-[12.5px] font-semibold"
              >
                <span className="font-bold">✓</span>
                {s}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
