"use client";

import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

import apiClient from "@/lib/api/client";

export default function DeleteAccountSection() {
  const { instance } = useMsal();
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") closeModal();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function closeModal() {
    if (deleting) return;
    setOpen(false);
    setError(null);
  }

  async function handleConfirmDelete() {
    setDeleting(true);
    setError(null);
    try {
      await apiClient.delete("/profile");
      void instance.logoutRedirect();
    } catch {
      setError("Erreur lors de la suppression du compte. Réessaie.");
      setDeleting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-[10px] border border-profile bg-profile-surface px-4 py-2.5 text-sm font-semibold text-destructive transition-colors hover:bg-profile-destructive-hover hover:border-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
      >
        Supprimer mon compte
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-scrim"
          onClick={closeModal}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-xl border border-default bg-surface p-6 shadow-2xl"
          >
            <h3 id="delete-account-title" className="text-lg font-semibold text-strong">
              Supprimer mon compte
            </h3>
            <p className="mt-2 text-sm text-body">
              Cette action supprime définitivement ton profil, tous tes CVs et
              l&apos;historique de tes correspondances. Elle est irréversible.
            </p>

            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={closeModal}
                disabled={deleting}
                className="rounded bg-solid-secondary px-4 py-2 text-sm text-primary transition-colors hover:bg-solid-secondary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmDelete()}
                disabled={deleting}
                className="rounded bg-solid-destructive px-4 py-2 text-sm text-on-solid transition-colors hover:bg-solid-destructive-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
              >
                {deleting ? "Suppression…" : "Supprimer définitivement"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
