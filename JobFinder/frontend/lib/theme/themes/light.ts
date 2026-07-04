import type { Theme } from "../types";

export const lightTheme: Theme = {
  /* Backgrounds */
  "--bg-page": "#ffffff",
  "--bg-surface": "#f3f4f6",
  "--bg-card": "rgba(0, 0, 0, 0.03)",
  "--bg-overlay": "rgba(0, 0, 0, 0.05)",
  "--bg-card-hover": "rgba(0, 0, 0, 0.07)",
  "--bg-badge": "rgba(0, 0, 0, 0.10)",
  "--bg-interactive": "rgba(0, 0, 0, 0.07)",
  "--bg-interactive-hover": "rgba(0, 0, 0, 0.13)",
  "--bg-destructive-muted": "rgba(239, 68, 68, 0.08)",
  "--bg-accent-muted": "rgba(37, 99, 235, 0.10)",
  "--bg-solid-primary": "rgb(37, 99, 235)",
  "--bg-solid-primary-hover": "rgb(29, 78, 216)",
  "--bg-solid-secondary": "rgba(0, 0, 0, 0.07)",
  "--bg-solid-secondary-hover": "rgba(0, 0, 0, 0.12)",
  "--bg-solid-destructive": "rgb(153, 27, 27)",
  "--bg-solid-destructive-hover": "rgb(220, 38, 38)",
  "--bg-solid-confirm": "rgb(22, 101, 52)",
  "--bg-solid-confirm-hover": "rgb(22, 163, 74)",
  "--bg-scrim": "rgba(0, 0, 0, 0.40)",
  "--bg-chip": "rgba(0, 0, 0, 0.03)",
  "--bg-dot-active": "rgba(0, 0, 0, 0.60)",

  /* Text */
  "--text-empty": "rgba(0, 0, 0, 0.20)",
  "--text-label": "rgba(0, 0, 0, 0.35)",
  "--text-hint": "rgba(0, 0, 0, 0.42)",
  "--text-muted": "rgba(0, 0, 0, 0.50)",
  "--text-secondary": "rgba(0, 0, 0, 0.62)",
  "--text-body": "rgba(0, 0, 0, 0.72)",
  "--text-primary": "rgba(0, 0, 0, 0.82)",
  "--text-strong": "rgba(0, 0, 0, 0.92)",
  "--text-success": "rgb(22, 163, 74)",
  "--text-warning": "rgb(180, 83, 9)",
  "--text-destructive": "rgba(220, 38, 38, 0.90)",
  "--text-accent": "rgb(37, 99, 235)",

  /* Borders */
  "--border-faint": "rgba(0, 0, 0, 0.07)",
  "--border-subtle": "rgba(0, 0, 0, 0.10)",
  "--border-soft": "rgba(0, 0, 0, 0.15)",
  "--border-default": "rgba(0, 0, 0, 0.22)",
  "--border-hover": "rgba(0, 0, 0, 0.45)",
  "--border-active": "rgba(0, 0, 0, 0.55)",
  "--border-accent": "rgba(37, 99, 235, 0.35)",

  /* Focus rings */
  "--ring-default": "rgba(0, 0, 0, 0.28)",
  "--ring-primary": "rgb(37, 99, 235)",
  "--ring-destructive": "rgb(220, 38, 38)",
  "--ring-confirm": "rgb(22, 163, 74)",

  /* Match / offer-card semantic */
  "--bg-match-skill":  "#e6f2ec",
  "--text-match-skill": "#12724e",
  "--bg-new-offer":    "rgb(253, 234, 234)",
  "--text-new-offer":  "rgb(200, 16, 46)",
  "--border-match":    "#1c7a56",
  "--text-on-solid":   "rgba(255, 255, 255, 0.95)",

  /* Canvas */
  "--canvas-ambient": "40, 60, 100",
  "--canvas-orbit": "20, 80, 200",
  "--canvas-icon": "#c8c8cc",
  "--canvas-icon-text": "50, 50, 70",
};
