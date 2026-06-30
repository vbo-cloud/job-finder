import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      backgroundColor: {
        page:                    "var(--bg-page)",
        surface:                 "var(--bg-surface)",
        card:                    "var(--bg-card)",
        overlay:                 "var(--bg-overlay)",
        "card-hover":            "var(--bg-card-hover)",
        badge:                   "var(--bg-badge)",
        interactive:             "var(--bg-interactive)",
        "interactive-hover":     "var(--bg-interactive-hover)",
        "destructive-muted":     "var(--bg-destructive-muted)",
        "accent-muted":          "var(--bg-accent-muted)",
        "solid-primary":         "var(--bg-solid-primary)",
        "solid-primary-hover":   "var(--bg-solid-primary-hover)",
        "solid-secondary":       "var(--bg-solid-secondary)",
        "solid-secondary-hover": "var(--bg-solid-secondary-hover)",
        "solid-destructive":     "var(--bg-solid-destructive)",
        "solid-destructive-hover": "var(--bg-solid-destructive-hover)",
        "solid-confirm":         "var(--bg-solid-confirm)",
        "solid-confirm-hover":   "var(--bg-solid-confirm-hover)",
      },
      textColor: {
        empty:       "var(--text-empty)",
        label:       "var(--text-label)",
        hint:        "var(--text-hint)",
        muted:       "var(--text-muted)",
        secondary:   "var(--text-secondary)",
        body:        "var(--text-body)",
        primary:     "var(--text-primary)",
        strong:      "var(--text-strong)",
        success:     "var(--text-success)",
        destructive: "var(--text-destructive)",
        accent:      "var(--text-accent)",
      },
      borderColor: {
        subtle:  "var(--border-subtle)",
        soft:    "var(--border-soft)",
        default: "var(--border-default)",
        hover:   "var(--border-hover)",
      },
      ringColor: {
        subtle:      "var(--border-subtle)",
        default:     "var(--ring-default)",
        primary:     "var(--ring-primary)",
        destructive: "var(--ring-destructive)",
        confirm:     "var(--ring-confirm)",
      },
    },
  },
  plugins: [],
};

export default config;
