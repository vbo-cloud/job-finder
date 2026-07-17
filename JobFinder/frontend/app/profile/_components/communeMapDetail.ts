import type { FeatureCollection } from "geojson";
import L from "leaflet";

import { CITY_LABELS } from "./cityLabels";
import { bboxIntersects, type Bbox, type CommuneFeature } from "./communeGeo";
import { contourStyle } from "./communeMapStyles";

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

/* Communes already labelled through the static city tiers — skip their
 * dynamic label to avoid doubled names. */
const CITY_NAMES = new Set(CITY_LABELS.map((c) => c.name));

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

export interface CityMarker {
  minZoom: number;
  name: string;
  marker: L.Marker;
}

/** Static big-city labels — created once, shown/hidden per zoom tier. */
export function createCityMarkers(): CityMarker[] {
  return CITY_LABELS.map((city) => ({
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
}

/** City labels appear progressively: the biggest cities are always
 * visible, medium ones only from their minZoom. */
export function syncCityLabels(map: L.Map, cityMarkers: CityMarker[]): void {
  const zoom = map.getZoom();
  for (const { marker, minZoom } of cityMarkers) {
    if (zoom >= minZoom) {
      if (!map.hasLayer(marker)) marker.addTo(map);
    } else if (map.hasLayer(marker)) {
      marker.remove();
    }
  }
}

export interface DetailLayersOptions {
  map: L.Map;
  /** Live geometry store — the caller keeps filling it as departments load. */
  communes: Map<string, CommuneFeature>;
  /** Shared canvas renderer of the paint layer (may not exist yet at call time). */
  getRenderer: () => L.Renderer | null;
  /** Static city labels already on screen — they reserve their collision box. */
  cityMarkers: CityMarker[];
  /** Called when the view is zoomed into detail level — lets the caller swap
   * visible departments for their 100m-simplified (HD) geometry. */
  upgradeVisibleDepts: (view: Bbox) => void;
}

export interface DetailLayers {
  /** Full detail pass: redraw visible commune contours and re-place labels. */
  sync: () => void;
  /** Debounced sync — fast successive pans/zooms only pay one full pass. */
  schedule: () => void;
  /** Re-apply the (theme-dependent) contour style to the current contours. */
  restyle: () => void;
  /** Remove every detail layer and cancel a pending scheduled sync. */
  dispose: () => void;
}

/**
 * High-zoom detail layers: contours of every visible commune from
 * CONTOUR_MIN_ZOOM, and name labels revealed progressively by population
 * (big towns first, then every village) — driven by the loaded dataset.
 */
export function createDetailLayers({
  map,
  communes,
  getRenderer,
  cityMarkers,
  upgradeVisibleDepts,
}: DetailLayersOptions): DetailLayers {
  let contoursLayer: L.GeoJSON | null = null;
  const communeLabelMarkers = new Map<string, L.Marker>();
  let detailTimer: ReturnType<typeof setTimeout> | undefined;

  const sync = () => {
    const zoom = map.getZoom();
    const b = map.getBounds();
    const view: Bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];

    contoursLayer?.remove();
    contoursLayer = null;
    if (zoom >= CONTOUR_MIN_ZOOM) {
      upgradeVisibleDepts(view);
      const features: CommuneFeature["feature"][] = [];
      communes.forEach((commune) => {
        if (bboxIntersects(commune.bbox, view)) features.push(commune.feature);
      });
      const collection: FeatureCollection = { type: "FeatureCollection", features };
      contoursLayer = L.geoJSON(collection, {
        style: () => ({
          ...contourStyle(),
          renderer: getRenderer() ?? undefined,
          interactive: false,
        }),
      }).addTo(map);
    }

    const visibleCodes = new Set<string>();
    if (zoom >= TOWN_LABEL_MIN_ZOOM) {
      const candidates: CommuneFeature[] = [];
      communes.forEach((commune) => {
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

  const schedule = () => {
    clearTimeout(detailTimer);
    detailTimer = setTimeout(sync, 50);
  };

  const restyle = () => {
    contoursLayer?.setStyle(contourStyle());
  };

  const dispose = () => {
    clearTimeout(detailTimer);
    contoursLayer?.remove();
    contoursLayer = null;
    communeLabelMarkers.forEach((marker) => marker.remove());
    communeLabelMarkers.clear();
  };

  return { sync, schedule, restyle, dispose };
}
