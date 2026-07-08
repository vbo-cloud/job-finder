"use client";

import type { MatchAnalysisOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";
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

const SECTION_TITLE_CLASS = "text-[10.5px] font-bold tracking-[.09em] uppercase text-muted";

/** Titled prose section; renders nothing when the agent left the field empty. */
function SummarySection({ title, text }: { title: string; text: string | null }) {
  if (!text) return null;
  return (
    <div>
      <p className={cn(SECTION_TITLE_CLASS, "mb-2")}>{title}</p>
      <p className="text-[13px] text-body leading-relaxed">{text}</p>
    </div>
  );
}

/** "Review de l'agent" column of an expanded MatchItem — pair analysis states + offer skills. */
export default function MatchAnalysisPanel({ analysis, analysisPending, onAnalyze, offerSkills }: Props) {
  const inProgress = analysisPending || analysis?.status === "processing";

  return (
    <div className="rounded-xl border border-faint bg-chip p-[18px]">
      {analysis?.status === "done" && analysis.verdict && (
        <p className="text-[15px] font-bold text-strong leading-snug mb-1.5">{analysis.verdict}</p>
      )}
      <p className={cn(SECTION_TITLE_CLASS, "mb-3.5")}>Review de l&apos;agent</p>

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
          <SummarySection title="Mission" text={analysis.mission_summary} />
          <SummarySection title="Entreprise" text={analysis.company_summary} />
          {(analysis.why_good_fit_for_user || analysis.why_good_candidate) && (
            <div>
              <p className={cn(SECTION_TITLE_CLASS, "mb-2")}>Pourquoi ça matche</p>
              <div className="flex flex-col gap-2.5">
                {analysis.why_good_fit_for_user && (
                  <div>
                    <p className="text-[12px] font-semibold text-strong mb-0.5">Pour vous</p>
                    <p className="text-[13px] text-body leading-relaxed">{analysis.why_good_fit_for_user}</p>
                  </div>
                )}
                {analysis.why_good_candidate && (
                  <div>
                    <p className="text-[12px] font-semibold text-strong mb-0.5">Pour eux</p>
                    <p className="text-[13px] text-body leading-relaxed">{analysis.why_good_candidate}</p>
                  </div>
                )}
              </div>
            </div>
          )}
          {analysis.score_explanation && (
            <div>
              <p className={cn(SECTION_TITLE_CLASS, "mb-2")}>Pourquoi ce score</p>
              <p className="text-[13px] text-muted leading-relaxed">{analysis.score_explanation}</p>
            </div>
          )}
          <AnalysisPointsList title="Points forts" items={analysis.points_forts} variant="positive" />
          <AnalysisPointsList
            title="Points d'amélioration"
            items={analysis.points_amelioration.map((p) => ({
              text: p.constat,
              suggestion: p.suggestion_concrete,
            }))}
            variant="negative"
          />
          {analysis.questions_entretien_potentielles.length > 0 && (
            <div>
              <p className={cn(SECTION_TITLE_CLASS, "mb-2")}>Questions d&apos;entretien potentielles</p>
              <ul className="flex flex-col gap-[7px] text-[13px] text-body leading-relaxed">
                {analysis.questions_entretien_potentielles.map((q) => (
                  <li key={q} className="flex gap-[9px]">
                    <span className="flex-none pt-px font-bold text-accent">?</span>
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
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
          <p className={cn(SECTION_TITLE_CLASS, "mt-[18px] mb-2.5")}>Compétences détectées</p>
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
