"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

const CONTRACT_TYPES = ["CDI", "CDD", "Freelance", "Stage", "Alternance"] as const;

export default function ProfilePage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const [location, setLocation] = useState("");
  const [contractTypes, setContractTypes] = useState<string[]>([]);
  const [jobCategories, setJobCategories] = useState<string[]>([]);
  const [jobCategoryInput, setJobCategoryInput] = useState("");
  const [romeCodes, setRomeCodes] = useState<string[]>([]);
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
        setContractTypes(res.data.contract_types);
        setJobCategories(res.data.job_categories);
        setRomeCodes(res.data.rome_codes);
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return; // no profile yet, empty form is correct
        console.error("[profile] GET /profile failed:", err);
        setLoadError("Erreur lors du chargement du profil.");
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  function toggleContractType(type: string) {
    setContractTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  }

  function addJobCategory() {
    const trimmed = jobCategoryInput.trim();
    if (trimmed && !jobCategories.includes(trimmed)) {
      setJobCategories((prev) => [...prev, trimmed]);
    }
    setJobCategoryInput("");
  }

  function removeJobCategory(cat: string) {
    setJobCategories((prev) => prev.filter((c) => c !== cat));
  }

  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      await apiClient.put("/profile", {
        location: location.trim() || null,
        contract_types: contractTypes,
        job_categories: jobCategories,
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

        <div>
          <p className="mb-2 text-sm font-medium text-primary">Types de contrat</p>
          <div className="flex flex-wrap gap-3">
            {CONTRACT_TYPES.map((type) => (
              <label key={type} className="flex cursor-pointer items-center gap-1.5 text-sm text-body">
                <input
                  type="checkbox"
                  checked={contractTypes.includes(type)}
                  onChange={() => toggleContractType(type)}
                  className="h-4 w-4 accent-[var(--bg-solid-primary)]"
                />
                {type}
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-primary">Catégories de poste</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={jobCategoryInput}
              onChange={(e) => setJobCategoryInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") {
                  e.preventDefault();
                  addJobCategory();
                }
              }}
              placeholder="ex. Développeur backend — Entrée ou virgule pour ajouter"
              className="flex-1 rounded border border-default bg-card px-3 py-2 text-sm text-strong placeholder:text-hint focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              type="button"
              onClick={addJobCategory}
              className="rounded bg-solid-secondary px-3 py-2 text-sm text-body hover:bg-solid-secondary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
            >
              Ajouter
            </button>
          </div>
          {jobCategories.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {jobCategories.map((cat) => (
                <span
                  key={cat}
                  className="flex items-center gap-1 rounded-full bg-accent-muted px-3 py-1 text-xs text-accent"
                >
                  {cat}
                  <button
                    type="button"
                    onClick={() => removeJobCategory(cat)}
                    className="ml-0.5 text-accent hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label={`Supprimer ${cat}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {romeCodes.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium text-primary">
              Codes ROME{" "}
              <span className="font-normal text-muted">(détectés depuis votre CV)</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {romeCodes.map((code) => (
                <span
                  key={code}
                  className="rounded-full bg-card px-3 py-1 text-xs text-body"
                >
                  {code}
                </span>
              ))}
            </div>
          </div>
        )}

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
