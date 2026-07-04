"use client";

import L from "leaflet";
import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";

import {
  communeIntersectsCircle,
  loadDepartementContours,
  loadDeptCommunes,
  loadDeptIndex,
  type CommuneFeature,
} from "./communeGeo";

/** Fixed on-screen brush radius — covers more communes the further the map is zoomed out. */
const BRUSH_RADIUS_PX = 24;

const EARTH_CIRCUMFERENCE_M = 40_075_016.686;

/** Reference cities rendered as labels — the stylised basemap has no tiles. */
const CITY_LABELS: [string, number, number][] = [
  ["Paris", 48.8566, 2.3522],
  ["Marseille", 43.2965, 5.3698],
  ["Lyon", 45.764, 4.8357],
  ["Toulouse", 43.6045, 1.4442],
  ["Nice", 43.7102, 7.262],
  ["Nantes", 47.2184, -1.5536],
  ["Montpellier", 43.6119, 3.8772],
  ["Strasbourg", 48.5734, 7.7521],
  ["Bordeaux", 44.8378, -0.5792],
  ["Lille", 50.6292, 3.0573],
  ["Rennes", 48.1173, -1.6778],
  ["Clermont-Ferrand", 45.7772, 3.087],
  ["Dijon", 47.322, 5.0415],
  ["Ajaccio", 41.9192, 8.7386],
];

interface CommunePaintLayerProps {
  value: string[];
  onChange: (codes: string[]) => void;
  /** Called once per brush stroke, before its first effective change — undo snapshot hook. */
  onStrokeStart: () => void;
  /** Called once when every commune geometry is loaded, with the full list of INSEE codes. */
  onCommunesLoaded: (codes: string[]) => void;
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

function departementStyle(): L.PathOptions {
  return {
    color: themeVar("--border-faint"),
    weight: 1,
    fill: true,
    fillColor: themeVar("--bg-card"),
    fillOpacity: 1,
  };
}

/**
 * Imperative Leaflet layer: a stylised France basemap (department contours and
 * city labels on the page background — no tiles) on which the user paints
 * whole communes with a circular brush. Left button paints, right button
 * erases, middle button pans, the wheel zooms toward the cursor. All commune
 * geometries load up front so painting works anywhere at any zoom; only the
 * selection is drawn. Must be rendered inside a react-leaflet MapContainer.
 */
export default function CommunePaintLayer({
  value,
  onChange,
  onStrokeStart,
  onCommunesLoaded,
}: CommunePaintLayerProps) {
  const map = useMap();
  const [pendingDepts, setPendingDepts] = useState<number | null>(null);

  const communesRef = useRef(new Map<string, CommuneFeature>());
  const selectionGroupRef = useRef<L.GeoJSON | null>(null);
  const selectionLayersRef = useRef(new Map<string, L.Layer>());
  const rendererRef = useRef<L.Renderer | null>(null);

  const selectedRef = useRef(new Set(value));
  selectedRef.current = new Set(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const onStrokeStartRef = useRef(onStrokeStart);
  onStrokeStartRef.current = onStrokeStart;
  const onCommunesLoadedRef = useRef(onCommunesLoaded);
  onCommunesLoadedRef.current = onCommunesLoaded;
  const strokeRef = useRef<"paint" | "erase" | null>(null);
  const strokeSnapshottedRef = useRef(false);
  const panPointRef = useRef<{ x: number; y: number } | null>(null);

  const addSelectionFill = (code: string) => {
    if (selectionLayersRef.current.has(code)) return;
    const commune = communesRef.current.get(code);
    if (!commune || !selectionGroupRef.current) return;
    // onEachFeature (below) registers the created sublayer in selectionLayersRef.
    selectionGroupRef.current.addData(commune.feature);
  };

  // Stylised basemap, commune geometries, selection layer, view lock.
  useEffect(() => {
    let cancelled = false;
    // The Map instance is stable — captured locally for the cleanup below.
    const selectionLayers = selectionLayersRef.current;
    const baseLayers: L.Layer[] = [];

    // The map is created with bounds fitting metropolitan France — forbid
    // zooming out further than that initial fit.
    map.setMinZoom(map.getZoom());

    // Departments render in a dedicated pane below the selection overlay.
    if (!map.getPane("franceBase")) {
      map.createPane("franceBase").style.zIndex = "350";
    }
    rendererRef.current = L.canvas({ padding: 0.3 });

    selectionGroupRef.current = L.geoJSON(undefined, {
      style: () => ({
        ...selectedStyle(),
        renderer: rendererRef.current ?? undefined,
        interactive: false,
      }),
      onEachFeature: (feature, lyr) =>
        selectionLayersRef.current.set(feature.properties.code as string, lyr),
    }).addTo(map);

    loadDepartementContours()
      .then((departements) => {
        if (cancelled) return;
        const baseRenderer = L.canvas({ padding: 0.3, pane: "franceBase" });
        const layer = L.geoJSON(departements, {
          pane: "franceBase",
          style: () => ({
            ...departementStyle(),
            renderer: baseRenderer,
            interactive: false,
          }),
        }).addTo(map);
        baseLayers.push(layer);
      })
      .catch((err: unknown) =>
        console.error("[CommunePaintLayer] loading departements failed:", err),
      );

    for (const [name, lat, lng] of CITY_LABELS) {
      const marker = L.marker([lat, lng], {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: "",
          html: `<span class="pointer-events-none whitespace-nowrap text-xs text-muted">${name}</span>`,
        }),
      }).addTo(map);
      baseLayers.push(marker);
    }

    loadDeptIndex()
      .then((index) => {
        if (cancelled) return;
        const depts = Object.keys(index);
        let remaining = depts.length;
        setPendingDepts(remaining);
        for (const dept of depts) {
          loadDeptCommunes(dept)
            .then((communes) => {
              if (cancelled) return;
              for (const commune of communes) communesRef.current.set(commune.code, commune);
              // Fill communes that were already selected (profile reload).
              selectedRef.current.forEach(addSelectionFill);
            })
            .catch((err: unknown) =>
              console.error(`[CommunePaintLayer] loading dept ${dept} failed:`, err),
            )
            .finally(() => {
              if (cancelled) return;
              remaining -= 1;
              setPendingDepts(remaining);
              if (remaining === 0) {
                onCommunesLoadedRef.current(Array.from(communesRef.current.keys()));
              }
            });
        }
      })
      .catch((err: unknown) => console.error("[CommunePaintLayer] loading index failed:", err));

    return () => {
      cancelled = true;
      for (const layer of baseLayers) layer.remove();
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
      if (!changed) return;
      // Snapshot the pre-stroke state exactly once, and only for strokes
      // that actually change something — keeps the undo history meaningful.
      if (!strokeSnapshottedRef.current) {
        strokeSnapshottedRef.current = true;
        onStrokeStartRef.current();
      }
      onChangeRef.current(Array.from(next));
    };

    const onMouseDown = (e: MouseEvent) => {
      // Clicks on Leaflet controls must not paint.
      if ((e.target as HTMLElement).closest(".leaflet-control-container")) return;
      if (e.button === 0) {
        strokeRef.current = "paint";
        strokeSnapshottedRef.current = false;
        setBrushAppearance(false);
        stamp(e, false);
        e.preventDefault();
      } else if (e.button === 2) {
        strokeRef.current = "erase";
        strokeSnapshottedRef.current = false;
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
