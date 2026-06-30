import type { Theme } from "./types";

export type { Theme } from "./types";
export { darkTheme } from "./themes/dark";
export { lightTheme } from "./themes/light";

/**
 * Applies a theme by writing its CSS variables to :root.
 * The dark theme defaults are baked into globals.css — call this only to switch themes.
 */
export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  (Object.entries(theme) as [string, string][]).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });
}
