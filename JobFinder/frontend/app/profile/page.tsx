"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

import DeleteAccountSection from "./_components/DeleteAccountSection";
import ExperienceToggle from "./_components/ExperienceToggle";
import { InfoTooltip } from "./_components/InfoTooltip";

export default function ProfilePage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();
  const account = accounts[0];
  const initials =
    account?.name
      ?.split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() ?? "?";

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [experienceLevel, setExperienceLevel] = useState<"0-2" | "2-5" | "5+" | null>(null);
  const [candidateDescription, setCandidateDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [analysisCredits, setAnalysisCredits] = useState<number | null>(null);

  function handleExperienceChange(next: "0-2" | "2-5" | "5+" | null) {
    setExperienceLevel(next);
    setSaved(false);
  }

  function handleDescriptionChange(next: string) {
    setCandidateDescription(next);
    setSaved(false);
  }

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    apiClient
      .get<ProfileData>("/profile")
      .then((res) => {
        setExperienceLevel(res.data.experience_level ?? null);
        setCandidateDescription(res.data.candidate_description ?? "");
        setAnalysisCredits(res.data.analysis_credits_remaining);
        setSaved(false);
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return; // no profile yet, empty form is correct
        console.error("[profile] GET /profile failed:", err);
        setLoadError("Erreur lors du chargement du profil.");
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      await apiClient.put("/profile", {
        experience_level: experienceLevel,
        candidate_description: candidateDescription.trim() || null,
      });
      setSaved(true);
    } catch {
      setSaveError("Erreur lors de la sauvegarde.");
    } finally {
      setSaving(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center">
        <h1 className="text-2xl font-bold text-strong">Profil</h1>
        <p className="text-body">Connectez-vous pour accéder à votre profil.</p>
        <button
          type="button"
          onClick={() => void instance.loginRedirect(loginRequest)}
          className="rounded bg-solid-primary px-5 py-2 text-on-solid hover:bg-solid-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Se connecter
        </button>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-muted">Chargement…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-destructive">{loadError}</p>
      </main>
    );
  }

  const microLabel = "text-[10.5px] font-bold uppercase tracking-[.09em] text-profile-muted";

  return (
    <div className="min-h-screen bg-profile-page">
      <div className="fixed inset-x-0 top-0 z-40 flex h-[52px] items-center bg-profile-surface px-5">
        <Link
          href="/"
          className="flex h-8 items-center gap-1 rounded-full border border-soft pl-2 pr-3.5 text-xs font-medium text-strong transition-colors hover:border-default hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={2.5} />
          Accueil
        </Link>
      </div>

      <main className="mx-auto max-w-4xl px-10 pb-16 pt-20">
        <div className="flex items-center gap-4">
          <div className="flex h-[60px] w-[60px] flex-none items-center justify-center rounded-2xl bg-accent-muted text-xl font-bold text-accent">
            {initials}
          </div>
          <div className="min-w-0">
            <div className={cn(microLabel, "mb-1")}>Mon profil</div>
            <h1 className="truncate text-xl font-bold leading-tight text-strong">
              {account?.name ?? "Mon profil"}
            </h1>
          </div>
        </div>

        {analysisCredits !== null && (
          <div className="mt-6 flex items-center gap-1.5 rounded-2xl bg-profile-surface p-6">
            <span className={microLabel}>Crédits d&apos;analyse restants</span>
            <InfoTooltip text="1 crédit = 1 analyse détaillée d'une offre par l'IA. 30 crédits offerts à l'inscription, cadeau de bienvenue bêta-testeur non renouvelable." />
            <span className="ml-auto text-lg font-bold text-strong">{analysisCredits}</span>
          </div>
        )}

        <div className="mt-6 rounded-2xl bg-profile-surface p-6">
          <div className="flex items-center gap-1.5">
            <span className={microLabel}>Expérience</span>
            <InfoTooltip text="Influence le score de pertinence des offres." />
          </div>
          <div className="mt-2.5">
            <ExperienceToggle value={experienceLevel} onChange={handleExperienceChange} />
          </div>

          <div className="mt-5 flex items-center gap-1.5">
            <label htmlFor="candidate-description" className={microLabel}>
              Informations complémentaires
            </label>
            <InfoTooltip text="Indiquez des informations complémentaires qui ne figurent pas dans votre CV. Elles influenceront le score de pertinence des offres." />
          </div>
          <textarea
            id="candidate-description"
            value={candidateDescription}
            onChange={(e) => handleDescriptionChange(e.target.value)}
            placeholder="Ex : Profil autodidacte · Recherche un poste en télétravail · Intérêt pour le cloud et l'IA…"
            rows={4}
            maxLength={1000}
            className="mt-2.5 w-full resize-y rounded-xl border border-profile bg-profile-page p-3.5 text-[13.5px] leading-relaxed text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          <p
            className={cn(
              "mt-2 text-right text-[11px] font-semibold text-profile-muted",
              candidateDescription.length >= 1000 && "text-destructive",
            )}
          >
            {candidateDescription.length} / 1000
          </p>

          {saveError && <p className="mt-3 text-sm text-destructive">{saveError}</p>}

          <div className="mt-4">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className={cn(
                "rounded-xl px-5 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50",
                saved
                  ? "border border-accent bg-accent-muted text-accent"
                  : "bg-solid-primary text-on-solid hover:bg-solid-primary-hover",
              )}
            >
              {saving ? "Enregistrement…" : saved ? "Enregistré ✓" : "Enregistrer"}
            </button>
          </div>
        </div>

        <div className="mt-6 border-t border-profile pt-6">
          <div className={cn(microLabel, "text-destructive opacity-70")}>Zone de suppression</div>
          <div className="mt-2.5 flex flex-col items-start gap-2">
            <DeleteAccountSection />
          </div>
        </div>
      </main>
    </div>
  );
}
