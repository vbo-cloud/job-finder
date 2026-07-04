"use client";

import "leaflet/dist/leaflet.css";

import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";

import { cn } from "@/lib/utils";

import CommunePaintLayer from "./CommunePaintLayer";

interface CommuneZonePickerProps {
  value: string[];
  onChange: (codes: string[]) => void;
}

const FRANCE_CENTER: [number, number] = [46.6, 2.4];
const FRANCE_ZOOM = 6;

/**
 * Map on which the user paints their job search zone commune by commune.
 * Selected INSEE codes are controlled by the parent through value/onChange.
 */
export default function CommuneZonePicker({ value, onChange }: CommuneZonePickerProps) {
  const [mode, setMode] = useState<"pan" | "paint">("pan");

  const modeButton = (target: "pan" | "paint", label: string) => (
    <button
      type="button"
      onClick={() => setMode(target)}
      aria-pressed={mode === target}
      className={cn(
        "rounded px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        mode === target
          ? "bg-solid-primary text-strong"
          : "bg-interactive text-body hover:bg-interactive-hover",
      )}
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {modeButton("pan", "Déplacer")}
        {modeButton("paint", "Peindre")}
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
        center={FRANCE_CENTER}
        zoom={FRANCE_ZOOM}
        scrollWheelZoom
        className="h-96 w-full rounded border border-default"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <CommunePaintLayer value={value} onChange={onChange} mode={mode} />
      </MapContainer>

      <p className="text-xs text-hint">
        Zoomez jusqu&apos;au niveau communal, activez « Peindre », puis glissez sur la carte pour
        sélectionner des communes entières. Un clic sur une commune sélectionnée la retire. Sans
        zone peinte, aucune restriction géographique n&apos;est appliquée.
      </p>
    </div>
  );
}
