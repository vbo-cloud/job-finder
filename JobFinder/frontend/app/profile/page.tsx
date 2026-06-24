"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";

const CONTRACT_TYPES = ["CDI", "CDD", "Freelance", "Stage", "Alternance"] as const;

interface ProfileData {
  user_id: string;
  rome_codes: string[];
  job_categories: string[];
  location: string | null;
  contract_types: string[];
}

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
        <h1 className="text-2xl font-bold">Profil</h1>
        <p className="text-gray-600">Connectez-vous pour accéder à votre profil.</p>
        <button
          type="button"
          onClick={() => void instance.loginRedirect(loginRequest)}
          className="rounded bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
        >
          Se connecter
        </button>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Chargement…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-red-600">{loadError}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Mon profil</h1>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Accueil
        </Link>
      </div>

      <div className="flex flex-col gap-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Localisation
          </label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="ex. Paris, Télétravail…"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Types de contrat</p>
          <div className="flex flex-wrap gap-3">
            {CONTRACT_TYPES.map((type) => (
              <label key={type} className="flex cursor-pointer items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={contractTypes.includes(type)}
                  onChange={() => toggleContractType(type)}
                  className="h-4 w-4 accent-blue-600"
                />
                {type}
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Catégories de poste</p>
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
              className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              type="button"
              onClick={addJobCategory}
              className="rounded bg-gray-100 px-3 py-2 text-sm hover:bg-gray-200"
            >
              Ajouter
            </button>
          </div>
          {jobCategories.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {jobCategories.map((cat) => (
                <span
                  key={cat}
                  className="flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-xs text-blue-800"
                >
                  {cat}
                  <button
                    type="button"
                    onClick={() => removeJobCategory(cat)}
                    className="ml-0.5 text-blue-500 hover:text-blue-700"
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
            <p className="mb-2 text-sm font-medium text-gray-700">
              Codes ROME{" "}
              <span className="font-normal text-gray-400">(détectés depuis votre CV)</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {romeCodes.map((code) => (
                <span
                  key={code}
                  className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
                >
                  {code}
                </span>
              ))}
            </div>
          </div>
        )}

        {feedback && (
          <p className={feedback.type === "success" ? "text-sm text-green-600" : "text-sm text-red-600"}>
            {feedback.message}
          </p>
        )}

        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="self-start rounded bg-blue-600 px-6 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </main>
  );
}
