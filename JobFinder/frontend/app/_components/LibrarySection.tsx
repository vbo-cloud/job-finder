"use client";

import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import type { CVData } from "@/lib/api/types";

import CVCard from "./CVCard";

const POLL_INTERVAL_MS = 3000;

interface Props {
  /** Increment to trigger a manual re-fetch (e.g. right after an upload). */
  refreshTrigger?: number;
}

export default function LibrarySection({ refreshTrigger = 0 }: Props) {
  const isAuthenticated           = useIsAuthenticated();
  const [cvs, setCvs]             = useState<CVData[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(false);

  const fetchCvs = useCallback(async (): Promise<void> => {
    try {
      const { data } = await apiClient.get<CVData[]>("/cv/");
      setCvs(data);
      setError(false);
    } catch (err) {
      console.error("[LibrarySection] fetch failed", err);
      setError(true);
    } finally {
      setLoading(false); // no-op on subsequent calls (already false)
    }
  }, []);

  // Only fetch when the user is authenticated; re-fetch when refreshTrigger changes
  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return; }
    void fetchCvs();
  }, [fetchCvs, isAuthenticated, refreshTrigger]);

  // Poll only while at least one CV is still being analysed
  useEffect(() => {
    if (!isAuthenticated) return;
    const hasPending = cvs.some(
      (cv) => cv.status === "pending" || cv.status === "processing",
    );
    if (!hasPending) return;

    const id = setInterval(() => void fetchCvs(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [cvs, fetchCvs, isAuthenticated]);

  return (
    <section
      id="library"
      className="h-dvh snap-start bg-[#0a0a0f] px-6 py-8"
    >
      <p className="mb-6 text-[9px] tracking-widest text-white/20">BIBLIOTHÈQUE</p>

      {loading && (
        <p className="text-xs text-white/20">Chargement…</p>
      )}

      {!loading && cvs.length === 0 && !error && (
        <p className="mt-24 text-center text-xs text-white/15">Aucun CV importé</p>
      )}

      {cvs.length > 0 && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {cvs.map((cv) => (
            <CVCard key={cv.id} cv={cv} />
          ))}
        </div>
      )}

      {error && (
        <p className="mt-4 text-xs text-red-400/50">Impossible de charger les CVs.</p>
      )}
    </section>
  );
}
