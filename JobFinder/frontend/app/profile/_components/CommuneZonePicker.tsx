"use client";

import "leaflet/dist/leaflet.css";

import type { LatLngBoundsExpression } from "leaflet";
import { useMemo } from "react";
import { MapContainer, TileLayer } from "react-leaflet";

import CommunePaintLayer from "./CommunePaintLayer";

interface CommuneZonePickerProps {
  value: string[];
  onChange: (codes: string[]) => void;
}

/** Metropolitan France (Corsica included) — initial fit and pan limits. */
const FRANCE_BOUNDS: LatLngBoundsExpression = [
  [41.2, -5.6],
  [51.3, 9.8],
];
const FRANCE_MAX_BOUNDS: LatLngBoundsExpression = [
  [40.0, -8.0],
  [52.5, 12.0],
];

/**
 * Map on which the user paints their job search zone commune by commune with
 * a circular brush. Selected INSEE codes are controlled by the parent through
 * value/onChange.
 */
export default function CommuneZonePicker({ value, onChange }: CommuneZonePickerProps) {
  // CARTO basemap flavor follows the active theme (dark_all / light_all).
  const tileStyle = useMemo(
    () =>
      getComputedStyle(document.documentElement).getPropertyValue("--map-tiles").trim() ||
      "dark_all",
    [],
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onChange([])}
          disabled={value.length === 0}
          className="rounded bg-solid-secondary px-3 py-1.5 text-sm text-body hover:bg-solid-secondary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Réinitialiser la zone
        </button>
        <span className="ml-auto text-sm text-muted">
          {value.length === 0
            ? "Aucune commune sélectionnée"
            : `${value.length} commune${value.length > 1 ? "s" : ""} sélectionnée${value.length > 1 ? "s" : ""}`}
        </span>
      </div>

      <MapContainer
        bounds={FRANCE_BOUNDS}
        maxBounds={FRANCE_MAX_BOUNDS}
        maxBoundsViscosity={1}
        zoomSnap={0.25}
        zoomControl={false}
        scrollWheelZoom
        dragging={false}
        doubleClickZoom={false}
        boxZoom={false}
        className="h-[30rem] w-full rounded border border-default"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url={`https://{s}.basemaps.cartocdn.com/${tileStyle}/{z}/{x}/{y}{r}.png`}
          subdomains="abcd"
        />
        <CommunePaintLayer value={value} onChange={onChange} />
      </MapContainer>

      <p className="text-xs text-hint">
        Clic gauche : peindre · clic droit : effacer · molette : zoomer sur le curseur · clic
        molette : déplacer. Le pinceau sélectionne toutes les communes qu&apos;il couvre —
        dézoomez pour élargir la surface peinte d&apos;un coup. Les contours communaux
        s&apos;affichent en zoomant, mais la peinture fonctionne à tout niveau. Sans zone peinte,
        aucune restriction géographique n&apos;est appliquée.
      </p>
    </div>
  );
}
