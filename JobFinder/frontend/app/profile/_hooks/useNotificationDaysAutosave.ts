"use client";

import { useCallback, useEffect, useRef } from "react";

import apiClient from "@/lib/api/client";

/**
 * Debounces `notification_days` edits into a silent background
 * `PUT /profile` — no "saved" indicator, failures are log-only (same
 * trade-off as HomeMapSection's commune_codes autosave). Decoupled from the
 * page's manual save flow: notification_days has no matching/cost impact,
 * unlike the _INTENT_FIELDS (routers/profile.py).
 */
export function useNotificationDaysAutosave(debounceMs: number) {
  // Refs, not state: dirtiness/debounce must not re-render the page — same
  // pattern as HomeMapSection's commune_codes autosave.
  const valueRef = useRef<number[]>([]);
  const dirtyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!dirtyRef.current) return;
    dirtyRef.current = false;
    apiClient
      .put("/profile", { notification_days: valueRef.current })
      .catch((err: unknown) => console.error("[profile] PUT /profile (notification_days) failed:", err));
  }, []);

  const schedule = useCallback(
    (next: number[]) => {
      valueRef.current = next;
      dirtyRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(flush, debounceMs);
    },
    [flush, debounceMs],
  );

  // Seeds the ref from the initial GET /profile — doesn't mark dirty, no PUT.
  const seed = useCallback((initial: number[]) => {
    valueRef.current = initial;
  }, []);

  // Best-effort flush on unmount — a tab close within the debounce window can
  // still lose the last toggle (same trade-off as HomeMapSection).
  useEffect(() => {
    return () => flush();
  }, [flush]);

  return { schedule, seed };
}
