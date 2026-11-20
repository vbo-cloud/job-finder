import type L from "leaflet";

/* Leaflet canvas paths cannot be styled through CSS classes — colors are read
 * from the theme CSS variables at style time (same exception as OrbitAnimation).
 * Callers must re-apply these styles when the theme switches (see the
 * MutationObserver in CommunePaintLayer). */
export function themeVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Fill + outline of a selected (painted) commune. */
export function selectedStyle(): L.PathOptions {
  return {
    color: themeVar("--border-accent"),
    weight: 1.5,
    fill: true,
    // The rgba token carries its own alpha — do not multiply it by Leaflet's default fillOpacity.
    fillColor: themeVar("--bg-accent-muted"),
    fillOpacity: 1,
  };
}

/** Department polygons of the stylised France basemap. */
export function departementStyle(): L.PathOptions {
  return {
    color: themeVar("--border-faint"),
    weight: 1,
    fill: true,
    fillColor: themeVar("--bg-card"),
    fillOpacity: 1,
  };
}

/** Commune contours revealed at detail zoom levels. */
export function contourStyle(): L.PathOptions {
  return { color: themeVar("--border-subtle"), weight: 1, fill: false };
}
