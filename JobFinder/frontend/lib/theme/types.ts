/**
 * Semantic color slots for the application theme.
 * Keys are CSS custom property names — applyTheme() writes them directly to :root.
 * Add a new key here, declare a default in globals.css, and register it in tailwind.config.ts.
 */
export type Theme = {
  /* Backgrounds */
  "--bg-page": string;
  "--bg-surface": string;
  "--bg-card": string;
  "--bg-overlay": string;
  "--bg-card-hover": string;
  "--bg-badge": string;
  "--bg-interactive": string;
  "--bg-interactive-hover": string;
  "--bg-destructive-muted": string;
  "--bg-accent-muted": string;
  "--bg-solid-primary": string;
  "--bg-solid-primary-hover": string;
  "--bg-solid-secondary": string;
  "--bg-solid-secondary-hover": string;
  "--bg-solid-destructive": string;
  "--bg-solid-destructive-hover": string;
  "--bg-solid-confirm": string;
  "--bg-solid-confirm-hover": string;
  "--bg-scrim": string;
  "--bg-chip": string;
  "--bg-dot-active": string;

  /* Text */
  "--text-empty": string;
  "--text-label": string;
  "--text-hint": string;
  "--text-muted": string;
  "--text-secondary": string;
  "--text-body": string;
  "--text-primary": string;
  "--text-strong": string;
  "--text-success": string;
  "--text-warning": string;
  "--text-destructive": string;
  "--text-accent": string;

  /* Borders */
  "--border-faint": string;
  "--border-subtle": string;
  "--border-soft": string;
  "--border-default": string;
  "--border-hover": string;
  "--border-active": string;
  "--border-accent": string;

  /* Focus rings */
  "--ring-default": string;
  "--ring-primary": string;
  "--ring-destructive": string;
  "--ring-confirm": string;

  /* Match / offer-card semantic */
  "--bg-match-skill": string;   /* background of matched-skill badges */
  "--text-match-skill": string; /* text of matched-skill badges */
  "--bg-new-offer": string;     /* background of "Nouveau" pill */
  "--text-new-offer": string;   /* text of "Nouveau" pill */
  "--border-match": string;     /* border of selected/expanded offer card */
  "--text-on-solid": string;    /* text on solid-color buttons (bg-solid-* family) — always light */

  /* Profile page (design handoff palette) */
  "--bg-profile-page": string;             /* page backdrop + textarea background */
  "--bg-profile-surface": string;          /* top bar, form section, toggle buttons, delete button */
  "--border-profile": string;              /* field borders (toggle, textarea, delete button, separator) */
  "--text-profile-muted": string;          /* micro-labels, character counter */
  "--bg-profile-destructive-hover": string; /* delete-account button hover fill */

  /* Canvas (OrbitAnimation — not usable as Tailwind utilities) */
  "--canvas-ambient": string;   /* RGB channels for ambient particle rgba() */
  "--canvas-orbit": string;     /* RGB channels for orbit particle rgba() */
  "--canvas-icon": string;      /* Solid color for the document icon body */
  "--canvas-icon-text": string; /* RGB channels for "CV" label and "+" cross */
};
