"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

import UnsavedChangesDialog from "@/app/_components/UnsavedChangesDialog";

interface UnsavedChangesContextValue {
  /** Called by the page that owns the dirty state on every edit / save / load. */
  setHasUnsavedChanges: (value: boolean) => void;
  /** Registered by that same page — invoked by the dialog's "Enregistrer et
   * quitter" button. Returns whether the save succeeded. `null` unregisters. */
  registerSaveHandler: (fn: (() => Promise<boolean>) | null) => void;
  /** Resolves `true` once it's safe to navigate: immediately if there are no
   * unsaved changes, or after the user picks "Enregistrer et quitter" /
   * "Quitter sans enregistrer" in the dialog. Resolves `false` on "Annuler". */
  confirmNavigation: () => Promise<boolean>;
}

const UnsavedChangesContext = createContext<UnsavedChangesContextValue | null>(null);

export function useUnsavedChanges(): UnsavedChangesContextValue {
  const ctx = useContext(UnsavedChangesContext);
  if (!ctx) {
    throw new Error("useUnsavedChanges must be used within UnsavedChangesProvider");
  }
  return ctx;
}

/**
 * Global guard against losing unsaved edits when navigating away from a page
 * that opts in via `setHasUnsavedChanges`/`registerSaveHandler` (currently
 * only `/profile`'s experience/description block — notifications auto-save
 * and never go through this). Mounted once in `app/layout.tsx` so that
 * globally-mounted navigation (MobileNavMenu) can consult it without knowing
 * anything about the page it might be leaving.
 */
export function UnsavedChangesProvider({ children }: { children: React.ReactNode }) {
  const dirtyRef = useRef(false);
  const saveHandlerRef = useRef<(() => Promise<boolean>) | null>(null);
  const resolveRef = useRef<((proceed: boolean) => void) | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  const setHasUnsavedChanges = useCallback((value: boolean) => {
    dirtyRef.current = value;
  }, []);

  const registerSaveHandler = useCallback((fn: (() => Promise<boolean>) | null) => {
    saveHandlerRef.current = fn;
  }, []);

  const confirmNavigation = useCallback((): Promise<boolean> => {
    if (!dirtyRef.current) return Promise.resolve(true);
    setSaveError(false);
    setDialogOpen(true);
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const settle = useCallback((proceed: boolean) => {
    setDialogOpen(false);
    resolveRef.current?.(proceed);
    resolveRef.current = null;
  }, []);

  const handleDiscard = useCallback(() => settle(true), [settle]);
  const handleCancel = useCallback(() => settle(false), [settle]);

  const handleSaveAndLeave = useCallback(async () => {
    const save = saveHandlerRef.current;
    if (!save) {
      settle(true);
      return;
    }
    setSaving(true);
    setSaveError(false);
    const ok = await save();
    setSaving(false);
    if (ok) {
      settle(true);
    } else {
      setSaveError(true);
    }
  }, [settle]);

  return (
    <UnsavedChangesContext.Provider
      value={{ setHasUnsavedChanges, registerSaveHandler, confirmNavigation }}
    >
      {children}
      {dialogOpen && (
        <UnsavedChangesDialog
          saving={saving}
          saveError={saveError}
          onSaveAndLeave={() => void handleSaveAndLeave()}
          onDiscard={handleDiscard}
          onCancel={handleCancel}
        />
      )}
    </UnsavedChangesContext.Provider>
  );
}
