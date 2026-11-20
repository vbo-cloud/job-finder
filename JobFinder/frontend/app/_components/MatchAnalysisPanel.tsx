"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import posthog from "posthog-js";
import apiClient from "@/lib/api/client";
import { InfoTooltip } from "@/components/InfoTooltip";
import type { MatchAnalysisOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import AnalysisPointsList from "./AnalysisPointsList";

interface Props {
  analysis: MatchAnalysisOut | null;
  analysisPending: boolean;
  /** Immediate request-level failure (e.g. credits exhausted) — distinct from analysis.status "error". */
  analysisError: string | null;
  /** True when analysisError came from a 402 — shows the "request more credits" CTA. */
  creditsExhausted: boolean;
  onAnalyze: () => void;
}

const ANALYZE_BUTTON_CLASS =
  "px-4 py-3 rounded-[10px] font-semibold text-[13.5px] border border-soft bg-page text-strong " +
  "hover:border-default transition-colors cursor-pointer " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default " +
  "disabled:cursor-default disabled:text-muted disabled:hover:border-soft";

const SECTION_TITLE_CLASS = "text-[10.5px] font-bold tracking-[.09em] uppercase text-muted";

/** "Je voudrais plus de crédits" CTA shown under the 0-credit error — a lightweight
 * interest signal (see docs/prompts/prompt-credits-signals-and-request-more.md), not a
 * real recharge flow. Swaps to a thank-you message once clicked, for this instance only. */
function MoreCreditsCta({ requested, onRequest }: { requested: boolean; onRequest: () => void }) {
  if (requested) {
    return <p className="text-[12px] text-body">Merci, votre demande a été transmise !</p>;
  }
  return (
    <button
      onClick={onRequest}
      className="px-3 py-2 rounded-[8px] font-semibold text-[12px] border border-soft bg-page text-strong hover:border-default transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
    >
      Je voudrais plus de crédits
    </button>
  );
}

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

/** "Review de l'agent" column of an expanded MatchItem — pair analysis states. */
export default function MatchAnalysisPanel({
  analysis, analysisPending, analysisError, creditsExhausted, onAnalyze,
}: Props) {
  // "pending" (queued, not yet claimed by a worker) must count as in-progress here
  // too, same as MatchItem's compact teaser — otherwise this panel would render the
  // "Analyser cette offre" button for a row that's already been enqueued (e.g. via
  // the server-side auto top-N on match creation), letting the user re-trigger it.
  const inProgress =
    analysisPending || analysis?.status === "processing" || analysis?.status === "pending";
  // Local to this panel instance, not this offer specifically — the request itself
  // is global to the user (see POST /profile/credits/request-more), so no need to
  // thread it back up through CorrespondancesPanel.
  const [moreCreditsRequested, setMoreCreditsRequested] = useState(false);

  function requestMoreCredits() {
    // Optimistic, same convention as onAnalyze/notifyCreditsReserved elsewhere in
    // this tree — the user doesn't need to know whether ACS actually sent the
    // email or the request was deduplicated by the cooldown.
    setMoreCreditsRequested(true);
    posthog.capture("more_credits_requested");
    apiClient.post("/profile/credits/request-more").catch((err: unknown) => {
      console.error("[jf] request-more-credits failed:", err);
    });
  }

  return (
    <div className="rounded-xl border border-faint bg-chip p-3.5 md:p-[18px]">
      {analysis?.status === "done" && analysis.verdict && (
        <p className="text-[15px] font-bold text-strong leading-snug mb-1.5">{analysis.verdict}</p>
      )}
      <div className="flex items-center gap-1.5 mb-3.5">
        <p className={SECTION_TITLE_CLASS}>Review de l&apos;agent</p>
        {!inProgress && analysis?.status === "done" && analysis.stale && (
          <>
            <span className="rounded-full border border-default px-2 py-0.5 text-[10px] font-bold uppercase tracking-[.03em] text-warning">
              Obsolète
            </span>
            <InfoTooltip text="L'analyse de cette offre n'a pas encore été actualisée depuis vos dernières modifications de votre profil." />
            <button
              onClick={onAnalyze}
              aria-label="Relancer l'analyse de cette offre (consomme 1 crédit)"
              className="flex h-5 w-5 items-center justify-center rounded-full text-muted transition-colors hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
            >
              <RefreshCw size={13} />
            </button>
          </>
        )}
      </div>

      {inProgress ? (
        <div className="flex flex-col items-center gap-3 py-2" role="status">
          <svg
            aria-hidden="true"
            className="h-6 w-6 animate-spin text-muted"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-[13.5px] font-semibold text-strong">Analyse en cours</span>
        </div>
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
        <div className="flex flex-col gap-3 items-center text-center">
          <p className="text-[13px] text-destructive leading-relaxed">
            L&apos;analyse a échoué — vous pouvez la relancer.
          </p>
          {/* analysisError here is a request-level failure on the retry itself
              (e.g. credits ran out before the user relaunched), not the
              agent-side failure the message above refers to — the two can
              legitimately show together. */}
          {analysisError && <p className="text-[12px] text-destructive">{analysisError}</p>}
          {creditsExhausted && (
            <MoreCreditsCta requested={moreCreditsRequested} onRequest={requestMoreCredits} />
          )}
          <button onClick={onAnalyze} className={ANALYZE_BUTTON_CLASS}>
            Analyser cette offre (consomme 1 crédit)
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3 items-center text-center">
          <p className="text-[13px] text-body leading-relaxed">
            Obtenez une analyse détaillée de votre CV face à cette offre : compétences
            correspondantes, points forts et pistes d&apos;amélioration.
          </p>
          {analysisError && <p className="text-[12px] text-destructive">{analysisError}</p>}
          {creditsExhausted && (
            <MoreCreditsCta requested={moreCreditsRequested} onRequest={requestMoreCredits} />
          )}
          <button onClick={onAnalyze} className={ANALYZE_BUTTON_CLASS}>
            Analyser cette offre avec l&apos;IA
          </button>
        </div>
      )}
    </div>
  );
}
