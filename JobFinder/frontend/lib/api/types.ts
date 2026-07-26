export type CVStatus = "pending" | "processing" | "done" | "matched" | "error";

export interface CVData {
  id: string;
  name: string | null;
  status: CVStatus;
  uploaded_at: string;
  match_count: number;
  unseen_count: number;
  has_thumbnail: boolean;
}

export interface CVUploadResponse {
  cv_id: string;
  message: string;
}

export interface RomeCodeEntry {
  cv_ids: string[];
  label: string;
}

export interface ProfileData {
  user_id: string;
  rome_codes: Record<string, RomeCodeEntry>;
  commune_codes: string[];
  experience_level: "0-2" | "2-5" | "5+" | null;
  candidate_description: string | null;
  /** ISO 8601 weekdays (1=lundi ... 7=dimanche) on which the email digest of
   * new offers per CV is sent. [] = notifications disabled. */
  notification_days: number[];
  /** Starts at 30 (beta welcome gift, non-renewable — ADR-018), decremented by
   * 1 per manual match analysis (POST /matches/.../analyze). Auto-triggered
   * analyses (top-N per matching run) never consume credits. */
  analysis_credits_remaining: number;
  /** True when the user is listed in the backend's ADMIN_USER_IDS — unlocks
   * admin-only UI such as the credits refill button on /profile. */
  is_admin: boolean;
}

export interface CreditsRefillResponse {
  analysis_credits_remaining: number;
}

export interface OfferOut {
  id: string;
  ft_id: string;
  title: string;
  company: string;
  location: string;
  contract_type: string;
  description: string;
  salary: string | null;
  rome_code: string | null;
  skills: string[];
  /** Essential technologies extracted by the match_analysis LLM, cached once per
   * offer. null = not yet extracted (no analysis has run on this offer yet);
   * [] = extracted, no essential technology identified. */
  key_skills: string[] | null;
  expires_at: string | null;
}

export interface CvAnalysisOut {
  status: "pending" | "processing" | "done" | "error";
  ats_score: number | null;
  synthese: string | null;
  points_forts: string[];
  points_faibles: string[];
  suggestions: string[];
  coherence_intention: string | null;
}

export interface PointAmelioration {
  constat: string;
  /** null only for analyses produced before migration 020 (legacy plain-string items). */
  suggestion_concrete: string | null;
}

export interface MatchAnalysisOut {
  status: "pending" | "processing" | "done" | "error";
  matched_skills: string[];
  points_forts: string[];
  points_amelioration: PointAmelioration[];
  synthese: string | null;
  verdict: string | null;
  company_summary: string | null;
  mission_summary: string | null;
  why_good_fit_for_user: string | null;
  why_good_candidate: string | null;
  score_explanation: string | null;
  questions_entretien_potentielles: string[];
  /** True when this "done" analysis predates the user's last intent change
   * (experience_level/candidate_description) — see routers/matches.py _mark_stale. */
  stale: boolean;
}

export interface MatchOut {
  score: number;
  offer: OfferOut;
  analysis: MatchAnalysisOut | null;
  is_new: boolean;
}

export interface CVMatchesOut {
  rome_codes: Record<string, RomeCodeEntry>;
  matches: MatchOut[];
}
