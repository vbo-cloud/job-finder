"use client";

import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { ChevronLeft, Frown, Meh, Smile } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

type FeedbackType = "avis" | "bug";
type Sentiment = "negatif" | "neutre" | "positif";
type SubmitState = "idle" | "loading" | "sent" | "error";

const SUBJECT_MAX_LENGTH = 200;
const MESSAGE_MAX_LENGTH = 5000;

// Mécontent -> content, left to right — matches the RESSENTI NEGATIF/NEUTRE/POSITIF
// order the backend prefixes onto the relayed message.
const SENTIMENT_OPTIONS: { value: Sentiment; label: string; Icon: typeof Frown }[] = [
  { value: "negatif", label: "Mécontent", Icon: Frown },
  { value: "neutre", label: "Neutre", Icon: Meh },
  { value: "positif", label: "Content", Icon: Smile },
];

export default function FeedbackPage() {
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  const [type, setType] = useState<FeedbackType>("avis");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sentiment, setSentiment] = useState<Sentiment | null>(null);
  const [state, setState] = useState<SubmitState>("idle");

  const microLabel = "text-[10.5px] font-bold uppercase tracking-[.09em] text-profile-muted";

  async function handleSubmit() {
    setState("loading");
    try {
      await apiClient.post("/feedback", {
        type,
        subject: subject.trim(),
        message: message.trim(),
        sentiment,
      });
      setState("sent");
      setSubject("");
      setMessage("");
      setSentiment(null);
    } catch {
      setState("error");
    }
  }

  if (!isAuthenticated) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center">
        <h1 className="text-2xl font-bold text-strong">Donner un avis / Signaler un bug</h1>
        <p className="text-body">Connectez-vous pour laisser un avis ou signaler un bug.</p>
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

  return (
    <div className="min-h-screen bg-profile-page">
      <div className="fixed inset-x-0 top-0 z-40 hidden h-[52px] items-center bg-profile-surface px-5 md:flex">
        <Link
          href="/"
          className="flex h-8 items-center gap-1 rounded-full border border-soft pl-2 pr-3.5 text-xs font-medium text-strong transition-colors hover:border-default hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={2.5} />
          Accueil
        </Link>
      </div>

      <main className="mx-auto max-w-2xl px-4 pb-16 pt-20 sm:px-10">
        <div className={cn(microLabel, "mb-1")}>Aide</div>
        <h1 className="text-xl font-bold leading-tight text-strong">
          Donner un avis / Signaler un bug
        </h1>

        <div className="mt-6 rounded-2xl bg-profile-surface p-4 sm:p-6">
          <div className="flex gap-2" role="radiogroup" aria-label="Type de retour">
            <button
              type="button"
              role="radio"
              aria-checked={type === "avis"}
              onClick={() => setType("avis")}
              className={cn(
                "flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                type === "avis"
                  ? "border-accent bg-accent-muted text-accent"
                  : "border-profile text-body hover:bg-overlay",
              )}
            >
              Avis
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={type === "bug"}
              onClick={() => setType("bug")}
              className={cn(
                "flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                type === "bug"
                  ? "border-accent bg-accent-muted text-accent"
                  : "border-profile text-body hover:bg-overlay",
              )}
            >
              Bug
            </button>
          </div>

          <div className="mt-5">
            <label htmlFor="feedback-subject" className={microLabel}>
              Sujet
            </label>
            <input
              id="feedback-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={SUBJECT_MAX_LENGTH}
              placeholder={type === "bug" ? "Ex : Le bouton d'envoi ne répond pas" : "Ex : Idée d'amélioration"}
              className="mt-2.5 w-full rounded-xl border border-profile bg-profile-page p-3.5 text-[13.5px] text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
          </div>

          <div className="mt-5">
            <label htmlFor="feedback-message" className={microLabel}>
              Message
            </label>
            <textarea
              id="feedback-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={6}
              maxLength={MESSAGE_MAX_LENGTH}
              placeholder={
                type === "bug"
                  ? "Décrivez le problème rencontré, les étapes pour le reproduire…"
                  : "Partagez votre avis ou une suggestion…"
              }
              className="mt-2.5 w-full resize-y rounded-xl border border-profile bg-profile-page p-3.5 text-[13.5px] leading-relaxed text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            <p
              className={cn(
                "mt-2 text-right text-[11px] font-semibold text-profile-muted",
                message.length >= MESSAGE_MAX_LENGTH && "text-destructive",
              )}
            >
              {message.length} / {MESSAGE_MAX_LENGTH}
            </p>
          </div>

          <div className="mt-5">
            <span className={microLabel}>Ressenti (facultatif)</span>
            <div className="mt-2.5 flex gap-2" role="group" aria-label="Ressenti">
              {SENTIMENT_OPTIONS.map(({ value, label, Icon }) => {
                const selected = sentiment === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={selected}
                    aria-label={label}
                    onClick={() => setSentiment(selected ? null : value)}
                    className={cn(
                      "flex flex-1 items-center justify-center rounded-xl border py-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                      selected
                        ? "border-accent bg-accent-muted text-accent"
                        : "border-profile text-body hover:bg-overlay",
                    )}
                  >
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </button>
                );
              })}
            </div>
          </div>

          {state === "error" && (
            <p className="mt-3 text-sm text-destructive">
              Erreur lors de l&apos;envoi. Réessayez plus tard.
            </p>
          )}

          <div className="mt-4">
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={state === "loading" || !subject.trim() || !message.trim()}
              className={cn(
                "rounded-xl px-5 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50",
                state === "sent"
                  ? "border border-accent bg-accent-muted text-accent"
                  : "bg-solid-primary text-on-solid hover:bg-solid-primary-hover",
              )}
            >
              {state === "loading" ? "Envoi…" : state === "sent" ? "Envoyé ✓" : "Envoyer"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
