"use client";

import "leaflet/dist/leaflet.css";

import type { LatLngBoundsExpression } from "leaflet";
import { Redo2, Undo2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { MapContainer } from "react-leaflet";

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

/** Undo/redo depth — one entry per brush stroke or toolbar action. */
const HISTORY_LIMIT = 50;

/**
 * Stylised France map (no tiles — department contours on the page background)
 * on which the user paints their job search zone commune by commune with a
 * circular brush. Selected INSEE codes are controlled by the parent through
 * value/onChange; undo/redo history is kept per brush stroke.
 */
export default function CommuneZonePicker({ value, onChange }: CommuneZonePickerProps) {
  const [past, setPast] = useState<string[][]>([]);
  const [future, setFuture] = useState<string[][]>([]);
  const [allCodes, setAllCodes] = useState<string[] | null>(null);

  const valueRef = useRef(value);
  valueRef.current = value;

  // Push the current selection on the undo stack — called by the paint layer
  // right before the first effective change of each brush stroke.
  const snapshot = useCallback(() => {
    setPast((p) => [...p.slice(-(HISTORY_LIMIT - 1)), valueRef.current]);
    setFuture([]);
  }, []);

  const handleCommunesLoaded = useCallback((codes: string[]) => setAllCodes(codes), []);

  const undo = () => {
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    setPast(past.slice(0, -1));
    setFuture([value, ...future].slice(0, HISTORY_LIMIT));
    onChange(previous);
  };

  const redo = () => {
    if (future.length === 0) return;
    const next = future[0];
    setFuture(future.slice(1));
    setPast([...past.slice(-(HISTORY_LIMIT - 1)), value]);
    onChange(next);
  };

  const selectAll = () => {
    if (!allCodes) return;
    snapshot();
    onChange(allCodes);
  };

  const reset = () => {
    snapshot();
    onChange([]);
  };

  const toolButtonClass =
    "rounded bg-solid-secondary px-3 py-1.5 text-sm text-body hover:bg-solid-secondary-hover disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={selectAll}
          disabled={allCodes === null}
          className={toolButtonClass}
        >
          Tout sélectionner
        </button>
        <button
          type="button"
          onClick={reset}
          disabled={value.length === 0}
          className={toolButtonClass}
        >
          Réinitialiser la zone
        </button>
        <button
          type="button"
          onClick={undo}
          disabled={past.length === 0}
          aria-label="Annuler le dernier coup de pinceau"
          className={toolButtonClass}
        >
          <Undo2 className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={redo}
          disabled={future.length === 0}
          aria-label="Rétablir le coup de pinceau annulé"
          className={toolButtonClass}
        >
          <Redo2 className="h-4 w-4" aria-hidden="true" />
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
        attributionControl={false}
        scrollWheelZoom
        dragging={false}
        doubleClickZoom={false}
        boxZoom={false}
        className="h-[30rem] w-full"
      >
        <CommunePaintLayer
          value={value}
          onChange={onChange}
          onStrokeStart={snapshot}
          onCommunesLoaded={handleCommunesLoaded}
        />
      </MapContainer>

      <p className="text-xs text-hint">
        Clic gauche : peindre · clic droit : effacer · molette : zoomer sur le curseur · clic
        molette : déplacer. Le pinceau sélectionne toutes les communes qu&apos;il couvre —
        dézoomez pour élargir la surface peinte d&apos;un coup. Sans zone peinte, aucune
        restriction géographique n&apos;est appliquée. Contours administratifs © Etalab / IGN
        (Licence Ouverte).
      </p>
    </div>
  );
}
