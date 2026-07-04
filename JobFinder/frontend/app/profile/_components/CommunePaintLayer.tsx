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

/** Below this zoom, unselected commune contours are not drawn (too many polygons).
 * Painting itself works at every zoom — the selection layer is always rendered. */
const CONTOUR_MIN_ZOOM = 7;

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

function selectedStyle(): L.PathOptions {
  return {
    color: themeVar("--border-accent"),
    weight: 1.5,
    fill: true,
    // The rgba token carries its own alpha — do not multiply it by Leaflet's default fillOpacity.
    fillColor: themeVar("--bg-accent-muted"),
    fillOpacity: 1,
  };
}

function contourStyle(): L.PathOptions {
  return { color: themeVar("--border-subtle"), weight: 1, fill: false };
}

/**
 * Imperative Leaflet layer that lets the user paint whole communes with a
 * circular brush: left button paints, right button erases, middle button
 * pans, the wheel zooms toward the cursor. All commune geometries are loaded
 * up front so painting works anywhere in France at any zoom; unselected
 * contours are only drawn from CONTOUR_MIN_ZOOM for performance.
 * Must be rendered inside a react-leaflet MapContainer.
 */
export default function CommunePaintLayer({ value, onChange }: CommunePaintLayerProps) {
  const map = useMap();
  const [pendingDepts, setPendingDepts] = useState<number | null>(null);

  const deptIndexRef = useRef<Record<string, Bbox> | null>(null);
  const deptFeaturesRef = useRef(new Map<string, CommuneFeature[]>());
  const communesRef = useRef(new Map<string, CommuneFeature>());
  const contourLayersRef = useRef(new Map<string, L.GeoJSON>());
  const selectionGroupRef = useRef<L.GeoJSON | null>(null);
  const selectionLayersRef = useRef(new Map<string, L.Layer>());
  const rendererRef = useRef<L.Renderer | null>(null);

  const selectedRef = useRef(new Set(value));
  selectedRef.current = new Set(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const strokeRef = useRef<"paint" | "erase" | null>(null);
  const panPointRef = useRef<{ x: number; y: number } | null>(null);

  const addSelectionFill = (code: string) => {
    if (selectionLayersRef.current.has(code)) return;
    const commune = communesRef.current.get(code);
    if (!commune || !selectionGroupRef.current) return;
    // onEachFeature (below) registers the created sublayer in selectionLayersRef.
    selectionGroupRef.current.addData(commune.feature);
  };

  // Load the geometry of every department, keep the view locked on France,
  // and draw unselected contours for the departments visible in the viewport.
  useEffect(() => {
    let cancelled = false;
    // The Map instances are stable — captured locally for the cleanup below.
    const contourLayers = contourLayersRef.current;
    const selectionLayers = selectionLayersRef.current;
    rendererRef.current = L.canvas({ padding: 0.3 });

    // The map is created with bounds fitting metropolitan France — forbid
    // zooming out further than that initial fit.
    map.setMinZoom(map.getZoom());

    selectionGroupRef.current = L.geoJSON(undefined, {
      style: () => ({
        ...selectedStyle(),
        renderer: rendererRef.current ?? undefined,
        interactive: false,
      }),
      onEachFeature: (feature, lyr) =>
        selectionLayersRef.current.set(feature.properties.code as string, lyr),
    }).addTo(map);

    const syncContourLayers = () => {
      const index = deptIndexRef.current;
      if (!index || map.getZoom() < CONTOUR_MIN_ZOOM) return;
      const b = map.getBounds();
      const view: Bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
      for (const [dept, bbox] of Object.entries(index)) {
        const communes = deptFeaturesRef.current.get(dept);
        if (!communes || !bboxIntersects(bbox, view) || contourLayersRef.current.has(dept)) {
          continue;
        }
        const collection: FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }> = {
          type: "FeatureCollection",
          features: communes.map((c) => c.feature),
        };
        const layer = L.geoJSON(collection, {
          // renderer/interactive are PathOptions — routed to each path via style().
          style: () => ({
            ...contourStyle(),
            renderer: rendererRef.current ?? undefined,
            interactive: false,
          }),
        }).addTo(map);
        contourLayersRef.current.set(dept, layer);
      }
    };

    loadDeptIndex()
      .then((index) => {
        if (cancelled) return;
        deptIndexRef.current = index;
        const depts = Object.keys(index);
        setPendingDepts(depts.length);
        for (const dept of depts) {
          loadDeptCommunes(dept)
            .then((communes) => {
              if (cancelled) return;
              deptFeaturesRef.current.set(dept, communes);
              for (const commune of communes) communesRef.current.set(commune.code, commune);
              // Fill communes that were already selected (profile reload).
              selectedRef.current.forEach(addSelectionFill);
              syncContourLayers();
            })
            .catch((err: unknown) =>
              console.error(`[CommunePaintLayer] loading dept ${dept} failed:`, err),
            )
            .finally(() => {
              if (!cancelled) setPendingDepts((n) => (n ?? 1) - 1);
            });
        }
      })
      .catch((err: unknown) => console.error("[CommunePaintLayer] loading index failed:", err));

    map.on("moveend", syncContourLayers);
    return () => {
      cancelled = true;
      map.off("moveend", syncContourLayers);
      contourLayers.forEach((layer) => layer.remove());
      contourLayers.clear();
      selectionGroupRef.current?.remove();
      selectionLayers.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  // Reflect the controlled selection on the always-visible selection layer.
  useEffect(() => {
    const selected = new Set(value);
    const toRemove: string[] = [];
    selectionLayersRef.current.forEach((_, code) => {
      if (!selected.has(code)) toRemove.push(code);
    });
    for (const code of toRemove) {
      const layer = selectionLayersRef.current.get(code);
      if (layer) selectionGroupRef.current?.removeLayer(layer);
      selectionLayersRef.current.delete(code);
    }
    selected.forEach(addSelectionFill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      const visible = x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
      brush.style.display = visible ? "block" : "none";
      brush.style.transform = `translate(${x - BRUSH_RADIUS_PX}px, ${y - BRUSH_RADIUS_PX}px)`;
    };

    const stamp = (e: MouseEvent, erase: boolean) => {
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
      // Clicks on Leaflet controls (attribution links) must not paint.
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

  if (pendingDepts !== null && pendingDepts <= 0) return null;
  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-[1000] flex justify-center">
      <span className="rounded border border-subtle bg-surface px-3 py-1.5 text-sm text-secondary">
        Chargement des communes…
      </span>
    </div>
  );
}
