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
