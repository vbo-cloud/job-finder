"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

// Leaflet touches window/document at import time — client-only.
const CommuneZonePicker = dynamic(() => import("./_components/CommuneZonePicker"), {
  ssr: false,
  loading: () => <div className="h-96 w-full animate-pulse rounded bg-card" />,
});

export default function ProfilePage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [communeCodes, setCommuneCodes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    apiClient
      .get<ProfileData>("/profile")
      .then((res) => {
        setCommuneCodes(res.data.commune_codes ?? []);
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
    setFeedback(null);
    try {
      await apiClient.put("/profile", {
        commune_codes: communeCodes,
      });
      setFeedback({ type: "success", message: "Profil enregistré." });
    } catch {
      setFeedback({ type: "error", message: "Erreur lors de la sauvegarde." });
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
          className="rounded bg-solid-primary px-5 py-2 text-strong hover:bg-solid-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
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

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-strong">Mon profil</h1>
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Accueil
        </Link>
      </div>

      <div className="flex flex-col gap-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-primary">
            Zone de recherche
          </label>
          <CommuneZonePicker value={communeCodes} onChange={setCommuneCodes} />
        </div>

        {feedback && (
          <p className={cn("text-sm", feedback.type === "success" ? "text-success" : "text-destructive")}>
            {feedback.message}
          </p>
        )}

        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="self-start rounded bg-solid-primary px-6 py-2 text-sm text-strong hover:bg-solid-primary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </main>
  );
}
