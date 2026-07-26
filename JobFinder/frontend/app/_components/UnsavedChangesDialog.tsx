"use client";

import { useEffect } from "react";

interface UnsavedChangesDialogProps {
  saving: boolean;
  saveError: boolean;
  onSaveAndLeave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
}

/**
 * Confirmation modal rendered by `UnsavedChangesProvider` when navigating
 * away from a page with unsaved changes (currently only `/profile`'s
 * experience/description block). Presentational only — all state lives in
 * the provider.
 */
export default function UnsavedChangesDialog({
  saving,
  saveError,
  onSaveAndLeave,
  onDiscard,
  onCancel,
}: UnsavedChangesDialogProps) {
  // Same pattern as DeleteAccountSection's confirm modal: Escape cancels,
  // disabled while a save is in flight.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !saving) onCancel();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [saving, onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="unsaved-changes-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-default bg-surface p-6 shadow-2xl"
      >
        <h3 id="unsaved-changes-title" className="text-lg font-semibold text-strong">
          Modifications non enregistrées
        </h3>
        <p className="mt-2 text-sm text-body">
          Vous avez des modifications non enregistrées. Quitter sans enregistrer ?
        </p>

        {saveError && (
          <p className="mt-3 text-sm text-destructive">Erreur lors de la sauvegarde.</p>
        )}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded bg-solid-secondary px-4 py-2 text-sm text-primary transition-colors hover:bg-solid-secondary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={onDiscard}
            disabled={saving}
            className="rounded bg-solid-destructive px-4 py-2 text-sm text-on-solid transition-colors hover:bg-solid-destructive-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
          >
            Quitter sans enregistrer
          </button>
          <button
            type="button"
            onClick={onSaveAndLeave}
            disabled={saving}
            className="rounded bg-solid-primary px-4 py-2 text-sm text-on-solid transition-colors hover:bg-solid-primary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {saving ? "Enregistrement…" : "Enregistrer et quitter"}
          </button>
        </div>
      </div>
    </div>
  );
}
