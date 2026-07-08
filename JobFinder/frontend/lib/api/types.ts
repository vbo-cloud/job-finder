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
  expires_at: string | null;
}

export interface CvAnalysisOut {
  status: "pending" | "processing" | "done" | "error";
  ats_score: number | null;
  points_forts: string[];
  points_faibles: string[];
  suggestions: string[];
  coherence_intention: string | null;
}

export interface MatchAnalysisOut {
  status: "pending" | "processing" | "done" | "error";
  matched_skills: string[];
  points_forts: string[];
  points_amelioration: string[];
  synthese: string | null;
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
