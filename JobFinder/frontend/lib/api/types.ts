export type CVStatus = "pending" | "processing" | "done" | "error";

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
  job_categories: string[];
  location: string | null;
  contract_types: string[];
}

export interface OfferOut {
  id: string;
  ft_id: string;
  title: string;
  company: string;
  location: string;
  contract_type: string;
  salary: string | null;
  rome_code: string | null;
  skills: string[];
  expires_at: string | null;
}

export interface MatchOut {
  score: number;
  offer: OfferOut;
}

export interface CVMatchesOut {
  rome_codes: Record<string, RomeCodeEntry>;
  matches: MatchOut[];
}
