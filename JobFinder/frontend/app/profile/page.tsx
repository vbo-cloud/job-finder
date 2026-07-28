"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import posthog from "posthog-js";
import { useCallback, useEffect, useState } from "react";

import { InfoTooltip } from "@/components/InfoTooltip";
import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { loginRequest } from "@/lib/auth/msalConfig";
import { useUnsavedChanges } from "@/lib/navigation/UnsavedChangesContext";
import { cn } from "@/lib/utils";

import AdminRefillButton from "./_components/AdminRefillButton";
import DeleteAccountSection from "./_components/DeleteAccountSection";
import ExperienceToggle from "./_components/ExperienceToggle";
import NotificationDaysToggle from "./_components/NotificationDaysToggle";
import { useNotificationDaysAutosave } from "./_hooks/useNotificationDaysAutosave";

/** Delay before auto-saving a notification-days edit — same order of
 * magnitude as HomeMapSection's commune_codes autosave (SAVE_DEBOUNCE_MS). */
const NOTIFICATION_DEBOUNCE_MS = 800;

export default function ProfilePage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();
  const router = useRouter();
  const { setHasUnsavedChanges, registerSaveHandler, confirmNavigation } = useUnsavedChanges();
  const account = instance.getActiveAccount() ?? accounts[0];
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
  const [notificationDays, setNotificationDays] = useState<number[]>([]);
  const [candidateDescription, setCandidateDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [analysisCredits, setAnalysisCredits] = useState<number | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  const { schedule: scheduleNotificationSave, seed: seedNotificationDays } =
    useNotificationDaysAutosave(NOTIFICATION_DEBOUNCE_MS);

  function handleExperienceChange(next: "0-2" | "2-5" | "5+" | null) {
    setExperienceLevel(next);
    setSaved(false);
    setDirty(true);
  }

  // Silent auto-save, decoupled from the Expérience/Description save flow —
  // notification_days has no matching/cost impact, unlike the _INTENT_FIELDS
  // (routers/profile.py), so it doesn't belong behind the manual "Enregistrer"
  // button or the unsaved-changes guard below.
  function handleNotificationDaysChange(next: number[]) {
    setNotificationDays(next);
    scheduleNotificationSave(next);
  }

  function handleDescriptionChange(next: string) {
    setCandidateDescription(next);
    setSaved(false);
    setDirty(true);
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
        const days = res.data.notification_days ?? [];
        setNotificationDays(days);
        seedNotificationDays(days);
        setCandidateDescription(res.data.candidate_description ?? "");
        setAnalysisCredits(res.data.analysis_credits_remaining);
        setIsAdmin(res.data.is_admin);
        setSaved(false);
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return; // no profile yet, empty form is correct
        console.error("[profile] GET /profile failed:", err);
        setLoadError("Erreur lors du chargement du profil.");
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated, seedNotificationDays]);

  // Returns whether the save succeeded — also used as the registered save
  // handler for the "Enregistrer et quitter" button of the unsaved-changes
  // dialog (UnsavedChangesContext), not just the in-page button below.
  const handleSave = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    try {
      await apiClient.put("/profile", {
        experience_level: experienceLevel,
        candidate_description: candidateDescription.trim() || null,
      });
      posthog.setPersonProperties({ experience_level: experienceLevel });
      posthog.capture("profile_completed", { experience_level: experienceLevel });
      setSaved(true);
      setDirty(false);
      return true;
    } catch {
      setSaveError("Erreur lors de la sauvegarde.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [experienceLevel, candidateDescription]);

  // Keeps the global guard in sync with this page's dirty state, registers
  // this page's save as the dialog's "Enregistrer et quitter" handler, and
  // clears both on unmount so a later navigation from elsewhere never sees a
  // stale "unsaved" flag (e.g. the browser back/forward case this feature
  // deliberately doesn't intercept, cf. profile page prompt).
  useEffect(() => {
    setHasUnsavedChanges(dirty);
  }, [dirty, setHasUnsavedChanges]);

  useEffect(() => {
    registerSaveHandler(handleSave);
    return () => registerSaveHandler(null);
  }, [registerSaveHandler, handleSave]);

  useEffect(() => {
    return () => setHasUnsavedChanges(false);
  }, [setHasUnsavedChanges]);

  // Native browser exit (tab close/reload/external nav) — SPA navigation is
  // covered separately by confirmNavigation (Link below, MobileNavMenu).
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

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
      {/* Hidden below md: the global pinned mobile bar (layout.tsx) already
          occupies the top of the screen and its menu navigates back home —
          two stacked fixed bars would fight for the same space. */}
      <div className="fixed inset-x-0 top-0 z-40 hidden h-[52px] items-center bg-profile-surface px-5 md:flex">
        <Link
          href="/"
          onClick={(e) => {
            e.preventDefault();
            void confirmNavigation().then((proceed) => {
              if (proceed) router.push("/");
            });
          }}
          className="flex h-8 items-center gap-1 rounded-full border border-soft pl-2 pr-3.5 text-xs font-medium text-strong transition-colors hover:border-default hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={2.5} />
          Accueil
        </Link>
      </div>

      <main className="mx-auto max-w-4xl px-4 pb-16 pt-20 sm:px-10">
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
          <div className="mt-6 flex items-center gap-1.5 rounded-2xl bg-profile-surface p-4 sm:p-6">
            <span className={microLabel}>Crédits d&apos;analyse restants</span>
            <InfoTooltip text="1 crédit = 1 analyse détaillée d'une offre par l'IA. 30 crédits offerts à l'inscription, cadeau de bienvenue bêta-testeur non renouvelable." />
            <span className="ml-auto flex items-center gap-3">
              {isAdmin && <AdminRefillButton onRefilled={setAnalysisCredits} />}
              <span className="text-lg font-bold text-strong">{analysisCredits}</span>
            </span>
          </div>
        )}

        <div className="mt-6 rounded-2xl bg-profile-surface p-4 sm:p-6">
          <div className="flex items-center gap-1.5">
            <span className={microLabel}>Notifications</span>
            <InfoTooltip text="Recevez un email récapitulatif des nouvelles offres correspondant à vos CV, les jours cochés." />
          </div>
          <div className="mt-2.5">
            <NotificationDaysToggle value={notificationDays} onChange={handleNotificationDaysChange} />
          </div>
        </div>

        <div className="mt-6 rounded-2xl bg-profile-surface p-4 sm:p-6">
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
