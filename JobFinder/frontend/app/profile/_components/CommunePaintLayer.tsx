"use client";

import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import L from "leaflet";
import { useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";

import {
  bboxContains,
  bboxIntersects,
  loadDeptCommunes,
  loadDeptIndex,
  type Bbox,
  type CommuneFeature,
} from "./communeGeo";

/** Below this zoom, commune contours are neither loaded nor paintable. */
export const MIN_PAINT_ZOOM = 8;

/** Cursor travel (px) under which a mousedown+mouseup counts as a click, not a drag. */
const CLICK_TOLERANCE_PX = 5;

interface CommunePaintLayerProps {
  value: string[];
  onChange: (codes: string[]) => void;
  mode: "pan" | "paint";
}

/* Leaflet canvas paths cannot be styled through CSS classes — colors are read
 * from the theme CSS variables at style time (same exception as OrbitAnimation). */
function themeVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function communeStyle(selected: boolean): L.PathOptions {
  if (selected) {
    return {
      color: themeVar("--border-accent"),
      weight: 1.5,
      fill: true,
      // The rgba token carries its own alpha — do not multiply it by Leaflet's default fillOpacity.
      fillColor: themeVar("--bg-accent-muted"),
      fillOpacity: 1,
    };
  }
  return { color: themeVar("--border-subtle"), weight: 1, fill: false };
}

/**
 * Imperative Leaflet layer that loads commune contours for the departments
 * visible in the viewport and lets the user paint/unpaint whole communes.
 * Must be rendered inside a react-leaflet MapContainer.
 */
export default function CommunePaintLayer({ value, onChange, mode }: CommunePaintLayerProps) {
  const map = useMap();

  const deptIndexRef = useRef<Record<string, Bbox> | null>(null);
  const loadedDeptsRef = useRef(new Set<string>());
  const communesRef = useRef(new Map<string, CommuneFeature>());
  const layersRef = useRef(new Map<string, L.Path>());
  const rendererRef = useRef<L.Renderer | null>(null);

  const selectedRef = useRef(new Set(value));
  selectedRef.current = new Set(value);
  const paintingRef = useRef(false);
  const draggedRef = useRef(false);
  const downPointRef = useRef<L.Point | null>(null);
  const styledSelectionRef = useRef(new Set<string>());

  useEffect(() => {
    let cancelled = false;
    const deptLayers: L.GeoJSON[] = [];
    rendererRef.current = L.canvas({ padding: 0.3 });

    const syncVisibleDepts = () => {
      const index = deptIndexRef.current;
      if (!index || map.getZoom() < MIN_PAINT_ZOOM) return;
      const b = map.getBounds();
      const view: Bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
      for (const [dept, bbox] of Object.entries(index)) {
        if (!bboxIntersects(bbox, view) || loadedDeptsRef.current.has(dept)) continue;
        loadedDeptsRef.current.add(dept);
        loadDeptCommunes(dept)
          .then((communes) => {
            if (cancelled) return;
            for (const commune of communes) communesRef.current.set(commune.code, commune);
            const collection: FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }> = {
              type: "FeatureCollection",
              features: communes.map((c) => c.feature),
            };
            const layer = L.geoJSON(collection, {
              // renderer/interactive are PathOptions — routed to each path via style().
              style: (feature) => ({
                ...communeStyle(selectedRef.current.has(feature?.properties.code as string)),
                renderer: rendererRef.current ?? undefined,
                interactive: false,
              }),
              onEachFeature: (feature, lyr) =>
                layersRef.current.set(feature.properties.code as string, lyr as L.Path),
            }).addTo(map);
            deptLayers.push(layer);
          })
          .catch((err: unknown) => {
            loadedDeptsRef.current.delete(dept);
            console.error(`[CommunePaintLayer] loading dept ${dept} failed:`, err);
          });
      }
    };

    loadDeptIndex()
      .then((index) => {
        if (cancelled) return;
        deptIndexRef.current = index;
        syncVisibleDepts();
      })
      .catch((err: unknown) => console.error("[CommunePaintLayer] loading index failed:", err));

    map.on("moveend", syncVisibleDepts);
    return () => {
      cancelled = true;
      map.off("moveend", syncVisibleDepts);
      for (const layer of deptLayers) layer.remove();
    };
  }, [map]);

  // Reflect the controlled selection on the rendered communes. Only layers whose
  // state actually changed are restyled — a full pass over every loaded polygon
  // on each paint stroke stalls the canvas renderer.
  useEffect(() => {
    const selected = new Set(value);
    const previous = styledSelectionRef.current;
    selected.forEach((code) => {
      if (!previous.has(code)) layersRef.current.get(code)?.setStyle(communeStyle(true));
    });
    previous.forEach((code) => {
      if (!selected.has(code)) layersRef.current.get(code)?.setStyle(communeStyle(false));
    });
    styledSelectionRef.current = selected;
  }, [value]);

  // Paint mode suspends map dragging so mousedown+drag paints instead of panning.
  useEffect(() => {
    if (mode === "paint") {
      map.dragging.disable();
      map.getContainer().style.cursor = "crosshair";
    } else {
      map.dragging.enable();
      map.getContainer().style.cursor = "";
    }
  }, [map, mode]);

  const communesAt = (latlng: L.LatLng): CommuneFeature[] => {
    const result: CommuneFeature[] = [];
    communesRef.current.forEach((commune) => {
      if (
        bboxContains(commune.bbox, latlng.lng, latlng.lat) &&
        booleanPointInPolygon([latlng.lng, latlng.lat], commune.feature)
      ) {
        result.push(commune);
      }
    });
    return result;
  };

  const paintAt = (latlng: L.LatLng) => {
    const toAdd = communesAt(latlng).filter((c) => !selectedRef.current.has(c.code));
    if (toAdd.length === 0) return;
    onChange(Array.from(selectedRef.current).concat(toAdd.map((c) => c.code)));
  };

  const toggleAt = (latlng: L.LatLng) => {
    const communes = communesAt(latlng);
    if (communes.length === 0) return;
    const next = new Set(selectedRef.current);
    for (const { code } of communes) {
      if (next.has(code)) next.delete(code);
      else next.add(code);
    }
    onChange(Array.from(next));
  };

  useMapEvents({
    mousedown(e) {
      if (mode !== "paint" || map.getZoom() < MIN_PAINT_ZOOM) return;
      paintingRef.current = true;
      draggedRef.current = false;
      downPointRef.current = e.containerPoint;
    },
    mousemove(e) {
      if (!paintingRef.current) return;
      // A real click always wobbles a pixel or two — only paint past the tolerance.
      if (
        !draggedRef.current &&
        downPointRef.current &&
        e.containerPoint.distanceTo(downPointRef.current) < CLICK_TOLERANCE_PX
      ) {
        return;
      }
      draggedRef.current = true;
      paintAt(e.latlng);
    },
    mouseup(e) {
      if (!paintingRef.current) return;
      paintingRef.current = false;
      // A plain click (no drag) toggles: it deselects an already-painted commune.
      if (!draggedRef.current) toggleAt(e.latlng);
    },
    mouseout() {
      paintingRef.current = false;
    },
  });

  return null;
}
