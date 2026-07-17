"use client";

import L from "leaflet";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";

import { attachBrushInteractions, type TouchTool } from "./communeBrush";
import {
  bboxIntersects,
  buildFranceOutline,
  loadDepartementContours,
  loadDeptCommunes,
  loadDeptIndex,
  type Bbox,
  type CommuneFeature,
  type DeptIndexEntry,
  type SelectableCommune,
} from "./communeGeo";
import { createCityMarkers, createDetailLayers, syncCityLabels } from "./communeMapDetail";
import { departementStyle, selectedStyle, themeVar } from "./communeMapStyles";

interface CommunePaintLayerProps {
  value: string[];
  onChange: (codes: string[]) => void;
  /** Called once per brush stroke, before its first effective change — undo snapshot hook. */
  onStrokeStart: () => void;
  /** Called once when every commune geometry is loaded, with the full commune
   * list and the department code → name mapping. */
  onCommunesLoaded: (communes: SelectableCommune[], deptNoms: Record<string, string>) => void;
  /** Called with true when a brush stroke starts (left or right button),
   * false when it ends — lets an embedding component ignore scroll while painting. */
  onPaintingChange?: (painting: boolean) => void;
  /** Called with true when the view is settled at the minimum zoom (fully
   * zoomed out), false as soon as a zoom starts or settles higher. Fired
   * once on mount with the initial state, then deduped. */
  onAtMinZoomChange?: (atMinZoom: boolean) => void;
  /** Increment to snap the view back to its initial nationwide fit — used
   * by the home page when leaving the map mode. */
  viewResetToken?: number;
  /** Active one-finger touch tool (see TouchTool in communeBrush). Defaults to "paint". */
  touchTool?: TouchTool;
}

/**
 * Imperative Leaflet layer: a stylised France basemap (department contours and
 * city labels on the page background — no tiles) on which the user paints
 * whole communes with a circular brush. Left button paints, right button
 * erases, middle button pans, the wheel zooms toward the cursor. On touch
 * screens one finger runs the `touchTool` (paint, erase or pan) and two
 * fingers always pinch-zoom/pan via Leaflet, whatever the tool. All commune
 * geometries load up front so painting works anywhere at any zoom; only the
 * selection is drawn. Must be rendered inside a react-leaflet MapContainer.
 *
 * The heavy lifting is delegated: brush/pointer interactions live in
 * communeBrush.ts, high-zoom contours and name labels in communeMapDetail.ts,
 * theme-token → Leaflet styles in communeMapStyles.ts. This component owns
 * the basemap, the data loading and the controlled-selection syncing.
 */
export default function CommunePaintLayer({
  value,
  onChange,
  onStrokeStart,
  onCommunesLoaded,
  onPaintingChange,
  onAtMinZoomChange,
  viewResetToken,
  touchTool = "paint",
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
  const onPaintingChangeRef = useRef(onPaintingChange);
  onPaintingChangeRef.current = onPaintingChange;
  const onAtMinZoomChangeRef = useRef(onAtMinZoomChange);
  onAtMinZoomChangeRef.current = onAtMinZoomChange;
  const touchToolRef = useRef(touchTool);
  touchToolRef.current = touchTool;
  const homeViewRef = useRef<{ center: L.LatLng; zoom: number } | null>(null);

  // Stable (only reads refs) so the effects below can list it as a
  // dependency without ever re-running because of it.
  const addSelectionFill = useCallback((code: string) => {
    if (selectionLayersRef.current.has(code)) return;
    const commune = communesRef.current.get(code);
    if (!commune || !selectionGroupRef.current) return;
    // onEachFeature (below) registers the created sublayer in selectionLayersRef.
    selectionGroupRef.current.addData(commune.feature);
  }, []);

  // Stylised basemap, commune geometries, selection layer, view lock.
  useEffect(() => {
    let cancelled = false;
    // The Map instance is stable — captured locally for the cleanup below.
    const selectionLayers = selectionLayersRef.current;
    const baseLayers: L.Layer[] = [];
    let departementsLayer: L.GeoJSON | null = null;

    // The map is created with bounds fitting metropolitan France — forbid
    // zooming out further than that initial fit, and remember that view as
    // the "home" position viewResetToken snaps back to.
    map.setMinZoom(map.getZoom());
    homeViewRef.current = { center: map.getCenter(), zoom: map.getZoom() };

    // Report whether the view is settled fully zoomed out — deduped,
    // initial state included (the map starts at its minimum zoom). A zoom
    // in flight is never "at min zoom": cleared as soon as a zoom starts,
    // re-synced when it ends — otherwise a quick zoom-in + scroll-down
    // would still read as "at min zoom" until the first zoomend.
    let atMinZoom: boolean | null = null;
    const reportAtMinZoom = (next: boolean) => {
      if (next === atMinZoom) return;
      atMinZoom = next;
      onAtMinZoomChangeRef.current?.(next);
    };
    const syncAtMinZoom = () => reportAtMinZoom(map.getZoom() <= map.getMinZoom());
    const clearAtMinZoom = () => reportAtMinZoom(false);
    syncAtMinZoom();
    map.on("zoomstart", clearAtMinZoom);
    map.on("zoomend", syncAtMinZoom);

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

    const cityMarkers = createCityMarkers();
    const doSyncCityLabels = () => syncCityLabels(map, cityMarkers);
    doSyncCityLabels();
    map.on("zoomend", doSyncCityLabels);
    for (const { marker } of cityMarkers) baseLayers.push(marker);

    // The arrow defers the resolution of upgradeVisibleDepts (defined below):
    // detail.sync() only ever runs from map events or load callbacks, long
    // after this effect body has finished.
    const detail = createDetailLayers({
      map,
      communes: communesRef.current,
      getRenderer: () => rendererRef.current,
      cityMarkers,
      upgradeVisibleDepts: (view) => upgradeVisibleDepts(view),
    });
    map.on("moveend", detail.schedule);

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
            detail.sync();
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
      detail.restyle();
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
                detail.sync();
              }
            });
        }
      })
      .catch((err: unknown) => console.error("[CommunePaintLayer] loading index failed:", err));

    return () => {
      cancelled = true;
      themeObserver.disconnect();
      map.off("zoomend", doSyncCityLabels);
      map.off("zoomstart", clearAtMinZoom);
      map.off("zoomend", syncAtMinZoom);
      map.off("moveend", detail.schedule);
      detail.dispose();
      for (const layer of baseLayers) layer.remove();
      selectionGroupRef.current?.remove();
      selectionLayers.clear();
    };
  }, [map, addSelectionFill]);

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
  }, [value, map, addSelectionFill]);

  // Snap back to the initial nationwide view. animate: false, twice over:
  // the change happens behind the home exit blur anyway, and an instant
  // jump cannot be left half-done by an interrupted zoom animation.
  useEffect(() => {
    if (!viewResetToken) return;
    const home = homeViewRef.current;
    if (home) map.setView(home.center, home.zoom, { animate: false });
  }, [viewResetToken, map]);

  // Brush interactions (mouse + touch) — see communeBrush.ts. The options
  // read through refs so the wiring never has to re-run on prop changes.
  useEffect(() => {
    return attachBrushInteractions(map, {
      getSelected: () => selectedRef.current,
      communes: communesRef.current,
      getTouchTool: () => touchToolRef.current,
      onStrokeStart: () => onStrokeStartRef.current(),
      onChange: (codes) => onChangeRef.current(codes),
      onPaintingChange: (painting) => onPaintingChangeRef.current?.(painting),
    });
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
