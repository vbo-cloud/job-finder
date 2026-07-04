"use client";

import type { FeatureCollection } from "geojson";
import L from "leaflet";
import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";

import { CITY_LABELS } from "./cityLabels";
import {
  bboxIntersects,
  buildFranceOutline,
  communeIntersectsCircle,
  loadDepartementContours,
  loadDeptCommunes,
  loadDeptIndex,
  type Bbox,
  type CommuneFeature,
  type DeptIndexEntry,
  type SelectableCommune,
} from "./communeGeo";

/** Fixed on-screen brush radius — covers more communes the further the map is zoomed out. */
const BRUSH_RADIUS_PX = 24;

/** From this zoom, the contours of every commune in the viewport are drawn
 * (e.g. the Paris arrondissements become visible) and the 100m-simplified
 * geometries are fetched per visible department to sharpen the rendering. */
const CONTOUR_MIN_ZOOM = 10;

/* Commune name labels appear progressively by population while zooming in,
 * ending with every village at COMMUNE_LABEL_MIN_ZOOM. */
const TOWN_LABEL_MIN_ZOOM = 9;
const TOWN_MIN_POP = 20_000;
const SMALL_TOWN_LABEL_MIN_ZOOM = 10;
const SMALL_TOWN_MIN_POP = 5_000;
const COMMUNE_LABEL_MIN_ZOOM = 11;

/* Municipal arrondissements ("Paris 12e Arrondissement") are labelled with
 * the short form ("12e") and only once their contours are drawn. */
const ARRONDISSEMENT_RE = /^(?:Paris|Lyon|Marseille) (\d+(?:er|e)) Arrondissement$/;

/* Labels are placed biggest-population-first and dropped when they would
 * overlap an already-placed one, so names fill in gradually as zooming in
 * frees screen space instead of a whole population tier popping at once.
 * Collision boxes are estimated from the name length. */
const LABEL_CHAR_PX = 7;
const LABEL_HEIGHT_PX = 20;
const LABEL_GAP_PX = 14;
const MAX_DYNAMIC_LABELS = 200;

/* The further the map is zoomed out, the more breathing room each label
 * demands — keeps dense areas (Île-de-France) down to a handful of names
 * instead of a wall of text. 1x from zoom 11.5 up. */
function labelSpacingScale(zoom: number): number {
  return 1 + Math.max(0, 11.5 - zoom) * 0.6;
}

interface PlacedLabel {
  x: number;
  y: number;
  halfW: number;
}

function labelCollides(
  placed: PlacedLabel[],
  x: number,
  y: number,
  halfW: number,
  scale: number,
): boolean {
  return placed.some(
    (p) =>
      Math.abs(y - p.y) < LABEL_HEIGHT_PX * scale &&
      Math.abs(x - p.x) < p.halfW + halfW + LABEL_GAP_PX * scale,
  );
}

const EARTH_CIRCUMFERENCE_M = 40_075_016.686;

/* Communes already labelled through the static city tiers — skip their
 * dynamic label to avoid doubled names. */
const CITY_NAMES = new Set(CITY_LABELS.map((c) => c.name));

interface CommunePaintLayerProps {
  value: string[];
  onChange: (codes: string[]) => void;
  /** Called once per brush stroke, before its first effective change — undo snapshot hook. */
  onStrokeStart: () => void;
  /** Called once when every commune geometry is loaded, with the full commune
   * list and the department code → name mapping. */
  onCommunesLoaded: (communes: SelectableCommune[], deptNoms: Record<string, string>) => void;
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

function contourStyle(): L.PathOptions {
  return { color: themeVar("--border-subtle"), weight: 1, fill: false };
}

/** Zoom from which a commune's name label is shown — lower for bigger towns. */
function labelMinZoom(commune: CommuneFeature): number {
  if (ARRONDISSEMENT_RE.test(commune.nom)) return CONTOUR_MIN_ZOOM;
  if (commune.pop >= TOWN_MIN_POP) return TOWN_LABEL_MIN_ZOOM;
  if (commune.pop >= SMALL_TOWN_MIN_POP) return SMALL_TOWN_LABEL_MIN_ZOOM;
  return COMMUNE_LABEL_MIN_ZOOM;
}

function communeLabelText(commune: CommuneFeature): string {
  return ARRONDISSEMENT_RE.exec(commune.nom)?.[1] ?? commune.nom;
}

function communeLabelIcon(commune: CommuneFeature): L.DivIcon {
  const nom = communeLabelText(commune);
  const sizeClass = commune.pop >= TOWN_MIN_POP ? "text-xs" : "text-[11px]";
  return L.divIcon({
    className: "",
    html:
      `<span class="pointer-events-none whitespace-nowrap ${sizeClass} text-muted" ` +
      `style="position:absolute;transform:translate(-50%,-50%)">${nom}</span>`,
  });
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
  const deptIndexRef = useRef<Record<string, DeptIndexEntry> | null>(null);
  const selectionGroupRef = useRef<L.GeoJSON | null>(null);
  const selectionLayersRef = useRef(new Map<string, L.Layer>());
  const rendererRef = useRef<L.Renderer | null>(null);
  const franceOutlineRef = useRef<L.Polyline | null>(null);

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
    let departementsLayer: L.GeoJSON | null = null;

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
        departementsLayer = L.geoJSON(departements, {
          pane: "franceBase",
          style: () => ({
            ...departementStyle(),
            renderer: baseRenderer,
            interactive: false,
          }),
        }).addTo(map);
        baseLayers.push(departementsLayer);

        // National outline shown while the selection is empty — empty zone
        // means "no geographic restriction", i.e. the whole of France.
        const outline = L.polyline(
          buildFranceOutline(departements).map((line) =>
            line.map(([lng, lat]) => [lat, lng] as [number, number]),
          ),
          {
            pane: "franceBase",
            renderer: baseRenderer,
            color: themeVar("--border-accent"),
            weight: 2.5,
            interactive: false,
          },
        );
        franceOutlineRef.current = outline;
        if (selectedRef.current.size === 0) outline.addTo(map);
        baseLayers.push(outline);
      })
      .catch((err: unknown) =>
        console.error("[CommunePaintLayer] loading departements failed:", err),
      );

    // City labels appear progressively: the biggest cities are always
    // visible, medium ones only from their minZoom.
    const cityMarkers = CITY_LABELS.map((city) => ({
      minZoom: city.minZoom,
      name: city.name,
      marker: L.marker([city.lat, city.lng], {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: "",
          html: `<span class="pointer-events-none whitespace-nowrap text-xs ${
            city.minZoom === 0 ? "text-secondary" : "text-muted"
          }">${city.name}</span>`,
        }),
      }),
    }));
    const syncCityLabels = () => {
      const zoom = map.getZoom();
      for (const { marker, minZoom } of cityMarkers) {
        if (zoom >= minZoom) {
          if (!map.hasLayer(marker)) marker.addTo(map);
        } else if (map.hasLayer(marker)) {
          marker.remove();
        }
      }
    };
    syncCityLabels();
    map.on("zoomend", syncCityLabels);
    for (const { marker } of cityMarkers) baseLayers.push(marker);

    // High-zoom detail: contours of every visible commune from
    // CONTOUR_MIN_ZOOM, and name labels revealed progressively by population
    // (big towns first, then every village) — driven by the loaded dataset.
    let contoursLayer: L.GeoJSON | null = null;
    const communeLabelMarkers = new Map<string, L.Marker>();
    const syncDetailLayers = () => {
      const zoom = map.getZoom();
      const b = map.getBounds();
      const view: Bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];

      contoursLayer?.remove();
      contoursLayer = null;
      if (zoom >= CONTOUR_MIN_ZOOM) {
        upgradeVisibleDepts(view);
        const features: CommuneFeature["feature"][] = [];
        communesRef.current.forEach((commune) => {
          if (bboxIntersects(commune.bbox, view)) features.push(commune.feature);
        });
        const collection: FeatureCollection = { type: "FeatureCollection", features };
        contoursLayer = L.geoJSON(collection, {
          style: () => ({
            ...contourStyle(),
            renderer: rendererRef.current ?? undefined,
            interactive: false,
          }),
        }).addTo(map);
      }

      const visibleCodes = new Set<string>();
      if (zoom >= TOWN_LABEL_MIN_ZOOM) {
        const candidates: CommuneFeature[] = [];
        communesRef.current.forEach((commune) => {
          if (
            zoom < labelMinZoom(commune) ||
            !bboxIntersects(commune.bbox, view) ||
            CITY_NAMES.has(commune.nom)
          ) {
            return;
          }
          candidates.push(commune);
        });
        // Biggest towns claim their spot first; the code tie-break keeps the
        // selection stable from one pan to the next.
        candidates.sort((a, b) => b.pop - a.pop || a.code.localeCompare(b.code));

        // The static city labels already on screen reserve their space.
        const placed: PlacedLabel[] = [];
        for (const city of cityMarkers) {
          if (zoom < city.minZoom) continue;
          const pt = map.latLngToContainerPoint(city.marker.getLatLng());
          placed.push({ x: pt.x, y: pt.y, halfW: (city.name.length * LABEL_CHAR_PX) / 2 });
        }

        const spacing = labelSpacingScale(zoom);
        for (const commune of candidates) {
          if (visibleCodes.size >= MAX_DYNAMIC_LABELS) break;
          const [w, s, e, n] = commune.bbox;
          const center = L.latLng((s + n) / 2, (w + e) / 2);
          const pt = map.latLngToContainerPoint(center);
          const halfW = (communeLabelText(commune).length * LABEL_CHAR_PX) / 2;
          if (labelCollides(placed, pt.x, pt.y, halfW, spacing)) continue;
          placed.push({ x: pt.x, y: pt.y, halfW });
          visibleCodes.add(commune.code);
          if (!communeLabelMarkers.has(commune.code)) {
            const marker = L.marker(center, {
              interactive: false,
              keyboard: false,
              icon: communeLabelIcon(commune),
            }).addTo(map);
            communeLabelMarkers.set(commune.code, marker);
          }
        }
      }
      communeLabelMarkers.forEach((marker, code) => {
        if (!visibleCodes.has(code)) {
          marker.remove();
          communeLabelMarkers.delete(code);
        }
      });
    };
    map.on("moveend", syncDetailLayers);

    // Once zoomed in, swap each visible department for its 100m-simplified
    // geometry (fetched once) so contours and selection match the zoom level —
    // the always-loaded 1000m set stays good enough for the country-wide view.
    const hdDepts = new Set<string>();
    const upgradeVisibleDepts = (view: Bbox) => {
      const index = deptIndexRef.current;
      if (!index) return;
      for (const [dept, entry] of Object.entries(index)) {
        // Overseas territories have no HD files — the map cannot reach them.
        if (hdDepts.has(dept) || /^9[78]/.test(dept) || !bboxIntersects(entry.bbox, view)) continue;
        hdDepts.add(dept);
        loadDeptCommunes(dept, true)
          .then((communes) => {
            if (cancelled) return;
            for (const commune of communes) communesRef.current.set(commune.code, commune);
            // Redraw the fills of already-selected communes with HD geometry.
            selectedRef.current.forEach((code) => {
              const layer = selectionLayersRef.current.get(code);
              if (!layer || communesRef.current.get(code)?.dept !== dept) return;
              selectionGroupRef.current?.removeLayer(layer);
              selectionLayersRef.current.delete(code);
              addSelectionFill(code);
            });
            syncDetailLayers();
          })
          .catch((err: unknown) => {
            hdDepts.delete(dept);
            console.error(`[CommunePaintLayer] loading HD dept ${dept} failed:`, err);
          });
      }
    };

    // Canvas paths capture their colors at style time — when the theme
    // switches (applyTheme rewrites the CSS variables on <html>), re-read
    // the tokens and re-style every themed layer. Labels and the brush use
    // CSS variables directly and follow the theme on their own.
    const restyleThemedLayers = () => {
      selectionGroupRef.current?.setStyle(selectedStyle());
      departementsLayer?.setStyle(departementStyle());
      contoursLayer?.setStyle(contourStyle());
      franceOutlineRef.current?.setStyle({ color: themeVar("--border-accent") });
    };
    const themeObserver = new MutationObserver(restyleThemedLayers);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["style"],
    });

    loadDeptIndex()
      .then((index) => {
        if (cancelled) return;
        deptIndexRef.current = index;
        const depts = Object.keys(index);
        let remaining = depts.length;
        setPendingDepts(remaining);
        for (const dept of depts) {
          loadDeptCommunes(dept)
            .then((communes) => {
              if (cancelled) return;
              for (const commune of communes) {
                // Never downgrade a commune already swapped to HD geometry.
                if (!communesRef.current.has(commune.code)) {
                  communesRef.current.set(commune.code, commune);
                }
              }
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
                const list = Array.from(communesRef.current.values(), (c) => ({
                  code: c.code,
                  nom: c.nom,
                  dept: c.dept,
                }));
                const deptNoms: Record<string, string> = {};
                for (const [dept, entry] of Object.entries(deptIndexRef.current ?? {})) {
                  deptNoms[dept] = entry.nom;
                }
                onCommunesLoadedRef.current(list, deptNoms);
                // The user may already be zoomed in on a detail level.
                syncDetailLayers();
              }
            });
        }
      })
      .catch((err: unknown) => console.error("[CommunePaintLayer] loading index failed:", err));

    return () => {
      cancelled = true;
      themeObserver.disconnect();
      map.off("zoomend", syncCityLabels);
      map.off("moveend", syncDetailLayers);
      contoursLayer?.remove();
      communeLabelMarkers.forEach((marker) => marker.remove());
      communeLabelMarkers.clear();
      for (const layer of baseLayers) layer.remove();
      selectionGroupRef.current?.remove();
      selectionLayers.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  // Reflect the controlled selection on the always-visible selection layer,
  // and swap the national outline in/out ("empty zone = whole country").
  useEffect(() => {
    const outline = franceOutlineRef.current;
    if (outline) {
      if (value.length === 0) {
        if (!map.hasLayer(outline)) outline.addTo(map);
      } else if (map.hasLayer(outline)) {
        outline.remove();
      }
    }

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
      // preventDefault() below suppresses the implicit focus — restore it so
      // Leaflet keyboard navigation (+/- and arrows) keeps working.
      container.focus({ preventScroll: true });
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
