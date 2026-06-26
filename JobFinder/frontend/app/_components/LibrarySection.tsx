"use client";

import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";
import type { CVData } from "@/lib/api/types";

import CVCard from "./CVCard";
import CVCardSkeleton from "./CVCardSkeleton";

const POLL_INTERVAL_MS = 3000;

interface Props {
  /** Increment to trigger a manual re-fetch (e.g. right after an upload). */
  refreshTrigger?: number;
}

export default function LibrarySection({ refreshTrigger = 0 }: Props) {
  const isAuthenticated           = useIsAuthenticated();
  const { instance }              = useMsal();
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
      setLoading(false);
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

      {/* État non connecté */}
      {!isAuthenticated && (
        <div className="flex flex-col items-center justify-center gap-6 pt-32">
          <p className="text-center text-sm text-white/35">
            Connectez-vous afin de pouvoir consulter<br />et charger des CV dans votre bibliothèque.
          </p>
          <button
            type="button"
            onClick={() => void instance.loginRedirect(loginRequest)}
            className="rounded-full border border-white/25 px-5 py-2 text-xs text-white/65 transition-colors hover:border-white/40 hover:text-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
          >
            Se connecter
          </button>
        </div>
      )}

      {/* Skeleton pendant le chargement initial */}
      {loading && isAuthenticated && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {[0, 1, 2].map((i) => <CVCardSkeleton key={i} />)}
        </div>
      )}

      {/* Aucun CV */}
      {!loading && isAuthenticated && cvs.length === 0 && !error && (
        <p className="mt-24 text-center text-xs text-white/15">Aucun CV importé</p>
      )}

      {/* Liste des CVs */}
      {cvs.length > 0 && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {cvs.map((cv) => (
            <CVCard key={cv.id} cv={cv} />
          ))}
        </div>
      )}

      {/* Erreur */}
      {isAuthenticated && error && (
        <p className="mt-4 text-xs text-red-400/50">Impossible de charger les CVs.</p>
      )}
    </section>
  );
}
