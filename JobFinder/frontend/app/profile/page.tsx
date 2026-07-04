"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

export default function ProfilePage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    apiClient
      .get<ProfileData>("/profile")
      .then((res) => {
        setLocation(res.data.location ?? "");
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
        location: location.trim() || null,
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
    <main className="mx-auto max-w-xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-strong">Mon profil</h1>
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Accueil
        </Link>
      </div>

      <div className="flex flex-col gap-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-primary">
            Localisation
          </label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="ex. Paris, Télétravail…"
            className="w-full rounded border border-default bg-card px-3 py-2 text-sm text-strong placeholder:text-hint focus:outline-none focus:ring-2 focus:ring-primary"
          />
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
