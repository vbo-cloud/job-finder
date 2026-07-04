"use client";

import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import L from "leaflet";
import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";

import {
  bboxIntersects,
  communeIntersectsCircle,
  loadDeptCommunes,
  loadDeptIndex,
  type Bbox,
  type CommuneFeature,
} from "./communeGeo";

/** Below this zoom, commune contours are neither loaded nor paintable. */
export const MIN_PAINT_ZOOM = 7;

/** Fixed on-screen brush radius — covers more communes the further the map is zoomed out. */
const BRUSH_RADIUS_PX = 24;

const EARTH_CIRCUMFERENCE_M = 40_075_016.686;

interface CommunePaintLayerProps {
  value: string[];
  onChange: (codes: string[]) => void;
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
 * visible in the viewport and lets the user paint whole communes with a
 * circular brush: left button paints, right button erases, middle button
 * pans, the wheel zooms. Must be rendered inside a react-leaflet MapContainer.
 */
export default function CommunePaintLayer({ value, onChange }: CommunePaintLayerProps) {
  const map = useMap();
  const [zoom, setZoom] = useState(() => map.getZoom());

  const deptIndexRef = useRef<Record<string, Bbox> | null>(null);
  const loadedDeptsRef = useRef(new Set<string>());
  const communesRef = useRef(new Map<string, CommuneFeature>());
  const layersRef = useRef(new Map<string, L.Path>());
  const rendererRef = useRef<L.Renderer | null>(null);

  const selectedRef = useRef(new Set(value));
  selectedRef.current = new Set(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const styledSelectionRef = useRef(new Set<string>());
  const strokeRef = useRef<"paint" | "erase" | null>(null);
  const panPointRef = useRef<{ x: number; y: number } | null>(null);

  // Load the contours of every department intersecting the viewport.
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

    const onZoomEnd = () => setZoom(map.getZoom());
    map.on("moveend", syncVisibleDepts);
    map.on("zoomend", onZoomEnd);
    return () => {
      cancelled = true;
      map.off("moveend", syncVisibleDepts);
      map.off("zoomend", onZoomEnd);
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

  // Mouse interactions: left = paint, right = erase, middle drag = pan.
  useEffect(() => {
    const container = map.getContainer();
    container.style.cursor = "crosshair";

    const brush = document.createElement("div");
    brush.style.cssText =
      `position:absolute;top:0;left:0;width:${BRUSH_RADIUS_PX * 2}px;height:${BRUSH_RADIUS_PX * 2}px;` +
      "border-radius:9999px;pointer-events:none;z-index:800;display:none;";
    const setBrushAppearance = (erasing: boolean) => {
      brush.style.border = `2px solid var(${erasing ? "--ring-destructive" : "--border-accent"})`;
      brush.style.background = `var(${erasing ? "--bg-destructive-muted" : "--bg-accent-muted"})`;
    };
    setBrushAppearance(false);
    container.appendChild(brush);

    const moveBrush = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const visible =
        x >= 0 && y >= 0 && x <= rect.width && y <= rect.height &&
        map.getZoom() >= MIN_PAINT_ZOOM;
      brush.style.display = visible ? "block" : "none";
      brush.style.transform = `translate(${x - BRUSH_RADIUS_PX}px, ${y - BRUSH_RADIUS_PX}px)`;
    };

    const stamp = (e: MouseEvent, erase: boolean) => {
      if (map.getZoom() < MIN_PAINT_ZOOM) return;
      const latlng = map.mouseEventToLatLng(e);
      const metersPerPixel =
        (EARTH_CIRCUMFERENCE_M * Math.abs(Math.cos((latlng.lat * Math.PI) / 180))) /
        Math.pow(2, map.getZoom() + 8);
      const radiusM = BRUSH_RADIUS_PX * metersPerPixel;

      const next = new Set(selectedRef.current);
      let changed = false;
      communesRef.current.forEach((commune) => {
        if (erase === next.has(commune.code) &&
            communeIntersectsCircle(commune, latlng.lng, latlng.lat, radiusM)) {
          if (erase) next.delete(commune.code);
          else next.add(commune.code);
          changed = true;
        }
      });
      if (changed) onChangeRef.current(Array.from(next));
    };

    const onMouseDown = (e: MouseEvent) => {
      // Clicks on Leaflet controls (zoom buttons, attribution) must not paint.
      if ((e.target as HTMLElement).closest(".leaflet-control-container")) return;
      if (e.button === 0) {
        strokeRef.current = "paint";
        setBrushAppearance(false);
        stamp(e, false);
        e.preventDefault();
      } else if (e.button === 2) {
        strokeRef.current = "erase";
        setBrushAppearance(true);
        stamp(e, true);
        e.preventDefault();
      } else if (e.button === 1) {
        panPointRef.current = { x: e.clientX, y: e.clientY };
        e.preventDefault(); // suppress browser autoscroll
      }
    };
    const onMouseMove = (e: MouseEvent) => {
      moveBrush(e);
      const panPoint = panPointRef.current;
      if (panPoint) {
        map.panBy([panPoint.x - e.clientX, panPoint.y - e.clientY], { animate: false });
        panPointRef.current = { x: e.clientX, y: e.clientY };
        return;
      }
      if (strokeRef.current) stamp(e, strokeRef.current === "erase");
    };
    const onMouseUp = () => {
      strokeRef.current = null;
      panPointRef.current = null;
      setBrushAppearance(false);
    };
    const onContextMenu = (e: MouseEvent) => e.preventDefault();
    const onMouseLeave = () => {
      brush.style.display = "none";
    };

    container.addEventListener("mousedown", onMouseDown);
    container.addEventListener("contextmenu", onContextMenu);
    container.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      container.removeEventListener("mousedown", onMouseDown);
      container.removeEventListener("contextmenu", onContextMenu);
      container.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      brush.remove();
      container.style.cursor = "";
    };
  }, [map]);

  if (zoom >= MIN_PAINT_ZOOM) return null;
  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-[1000] flex justify-center">
      <span className="rounded border border-subtle bg-surface px-3 py-1.5 text-sm text-secondary">
        Zoomez pour afficher et peindre les communes
      </span>
    </div>
  );
}
