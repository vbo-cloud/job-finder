export type CVStatus = "pending" | "processing" | "done" | "error";

export interface CVData {
  id: string;
  name: string | null;
  status: CVStatus;
  uploaded_at: string;
  match_count: number;
  thumbnail_url: string | null;
}

export interface CVUploadResponse {
  cv_id: string;
  message: string;
}

export interface ProfileData {
  user_id: string;
  rome_codes: string[];
  job_categories: string[];
  location: string | null;
  contract_types: string[];
}
