"use client";

import "leaflet/dist/leaflet.css";

import type { LatLngBoundsExpression } from "leaflet";
import { ChevronRight, Redo2, Undo2 } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { MapContainer } from "react-leaflet";

import CommunePaintLayer, { type SelectableCommune } from "./CommunePaintLayer";

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

/** Numeric department order, with Corsica (2A/2B) slotted after 20. */
function deptSortKey(dept: string): number {
  if (dept === "2A") return 20.1;
  if (dept === "2B") return 20.2;
  return Number.parseInt(dept, 10);
}

/**
 * Stylised France map (no tiles — department contours on the page background)
 * on which the user paints their job search zone commune by commune with a
 * circular brush. Selected INSEE codes are controlled by the parent through
 * value/onChange; undo/redo history is kept per brush stroke. The selection
 * is summarised live below the map, grouped by department.
 */
export default function CommuneZonePicker({ value, onChange }: CommuneZonePickerProps) {
  const [past, setPast] = useState<string[][]>([]);
  const [future, setFuture] = useState<string[][]>([]);
  const [communes, setCommunes] = useState<SelectableCommune[] | null>(null);
  const [deptNoms, setDeptNoms] = useState<Record<string, string>>({});
  const [openDepts, setOpenDepts] = useState<Set<string>>(new Set());

  const valueRef = useRef(value);
  valueRef.current = value;

  // Push the current selection on the undo stack — called by the paint layer
  // right before the first effective change of each brush stroke.
  const snapshot = useCallback(() => {
    setPast((p) => [...p.slice(-(HISTORY_LIMIT - 1)), valueRef.current]);
    setFuture([]);
  }, []);

  const handleCommunesLoaded = useCallback(
    (list: SelectableCommune[], noms: Record<string, string>) => {
      setCommunes(list);
      setDeptNoms(noms);
    },
    [],
  );

  const communeByCode = useMemo(
    () => new Map((communes ?? []).map((c) => [c.code, c])),
    [communes],
  );

  const deptTotals = useMemo(() => {
    const totals = new Map<string, number>();
    for (const c of communes ?? []) totals.set(c.dept, (totals.get(c.dept) ?? 0) + 1);
    return totals;
  }, [communes]);

  // Live selection summary: departments in numeric order; the commune lists
  // are only sorted (and rendered) for the departments the user unfolds.
  const selectedByDept = useMemo(() => {
    const groups = new Map<string, SelectableCommune[]>();
    for (const code of value) {
      const commune = communeByCode.get(code);
      if (!commune) continue;
      const group = groups.get(commune.dept);
      if (group) group.push(commune);
      else groups.set(commune.dept, [commune]);
    }
    return Array.from(groups.entries()).sort(
      (a, b) => deptSortKey(a[0]) - deptSortKey(b[0]) || a[0].localeCompare(b[0]),
    );
  }, [value, communeByCode]);

  const toggleDept = (dept: string) =>
    setOpenDepts((prev) => {
      const next = new Set(prev);
      if (next.has(dept)) next.delete(dept);
      else next.add(dept);
      return next;
    });

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
    if (!communes) return;
    snapshot();
    onChange(communes.map((c) => c.code));
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
          disabled={communes === null}
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
        maxZoom={14}
        zoomSnap={0.25}
        zoomControl={false}
        attributionControl={false}
        scrollWheelZoom
        dragging={false}
        doubleClickZoom={false}
        boxZoom={false}
        className="h-[50rem] w-full"
      >
        <CommunePaintLayer
          value={value}
          onChange={onChange}
          onStrokeStart={snapshot}
          onCommunesLoaded={handleCommunesLoaded}
        />
      </MapContainer>

      {selectedByDept.length > 0 && (
        <div className="max-h-80 overflow-y-auto rounded border border-subtle">
          {selectedByDept.map(([dept, list]) => {
            const open = openDepts.has(dept);
            const total = deptTotals.get(dept);
            return (
              <div key={dept} className="border-b border-subtle last:border-b-0">
                <button
                  type="button"
                  onClick={() => toggleDept(dept)}
                  aria-expanded={open}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-body hover:bg-solid-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <ChevronRight
                    className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? "rotate-90" : ""}`}
                    aria-hidden="true"
                  />
                  <span>
                    {dept} — {deptNoms[dept] ?? dept}
                  </span>
                  <span className="ml-auto text-xs text-muted">
                    {list.length}
                    {total !== undefined && ` / ${total}`} commune{list.length > 1 ? "s" : ""}
                  </span>
                </button>
                {open && (
                  <div className="flex flex-wrap gap-1.5 px-3 pb-3 pl-9">
                    {[...list]
                      .sort((a, b) => a.nom.localeCompare(b.nom, "fr"))
                      .map((commune) => (
                        <span
                          key={commune.code}
                          title={commune.code}
                          className="rounded bg-solid-secondary px-2 py-0.5 text-xs text-body"
                        >
                          {commune.nom}
                        </span>
                      ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-xs text-hint">
        Contours administratifs © Etalab / IGN (Licence Ouverte).
      </p>
    </div>
  );
}
