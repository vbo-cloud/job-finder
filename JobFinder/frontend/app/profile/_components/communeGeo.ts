import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from "geojson";

/** Bounding box as [west, south, east, north]. */
export type Bbox = [number, number, number, number];

export type CommuneGeometry = Feature<
  Polygon | MultiPolygon,
  { code: string; nom: string; pop: number }
>;

export interface CommuneFeature {
  code: string;
  nom: string;
  /** Population (0 when unknown) — drives the zoom level at which the name label appears. */
  pop: number;
  dept: string;
  bbox: Bbox;
  feature: CommuneGeometry;
}

const GEO_BASE = "/geo/communes";
const GEO_HD_BASE = "/geo/communes-hd";

/** Load the department contours used as the stylised basemap. */
export async function loadDepartementContours(): Promise<
  FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }>
> {
  const res = await fetch("/geo/departements.geojson");
  if (!res.ok) throw new Error(`Failed to load departement contours (HTTP ${res.status})`);
  return res.json() as Promise<
    FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }>
  >;
}

export interface DeptIndexEntry {
  bbox: Bbox;
  nom: string;
}

/** Commune identity used for the selection summary and zone compression. */
export interface SelectableCommune {
  code: string;
  nom: string;
  dept: string;
}

/** Storage token marking a fully-selected department (e.g. "dept:74"). */
export const DEPT_TOKEN_PREFIX = "dept:";

/**
 * Compress a plain INSEE code selection into the storage/API form: every
 * department whose communes are all selected collapses to its "dept:xx"
 * token. Codes missing from the referential pass through untouched.
 */
export function compressSelection(
  codes: string[],
  communeByCode: Map<string, SelectableCommune>,
  deptTotals: Map<string, number>,
): string[] {
  const byDept = new Map<string, string[]>();
  const out: string[] = [];
  for (const code of codes) {
    const commune = communeByCode.get(code);
    if (!commune) {
      out.push(code);
      continue;
    }
    const group = byDept.get(commune.dept);
    if (group) group.push(code);
    else byDept.set(commune.dept, [code]);
  }
  byDept.forEach((group, dept) => {
    if (group.length === deptTotals.get(dept)) out.push(`${DEPT_TOKEN_PREFIX}${dept}`);
    else out.push(...group);
  });
  return out;
}

/**
 * Expand "dept:xx" tokens back into plain INSEE codes. Tokens whose
 * department is not in the referential yet are returned in `unresolved`
 * so callers can carry them over to the next write instead of losing them.
 */
export function expandSelection(
  value: string[],
  codesByDept: Map<string, string[]>,
): { codes: string[]; unresolved: string[] } {
  const codes: string[] = [];
  const unresolved: string[] = [];
  for (const entry of value) {
    if (!entry.startsWith(DEPT_TOKEN_PREFIX)) {
      codes.push(entry);
      continue;
    }
    const deptCodes = codesByDept.get(entry.slice(DEPT_TOKEN_PREFIX.length));
    if (deptCodes) codes.push(...deptCodes);
    else unresolved.push(entry);
  }
  return { codes, unresolved };
}

/**
 * Outer boundary of the department collection, as GeoJSON [lng, lat] lines.
 * Internal borders are shared by two departments and appear twice; the
 * national outline edges appear exactly once — those survivors are chained
 * end-to-end into polylines.
 */
export function buildFranceOutline(
  departements: FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }>,
): Position[][] {
  const keyOf = (p: Position) => `${p[0].toFixed(4)},${p[1].toFixed(4)}`;
  const edges = new Map<string, { a: Position; b: Position; count: number }>();
  const visit = (ring: Position[]) => {
    for (let i = 0; i < ring.length - 1; i++) {
      const ka = keyOf(ring[i]);
      const kb = keyOf(ring[i + 1]);
      if (ka === kb) continue;
      const key = ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
      const edge = edges.get(key);
      if (edge) edge.count += 1;
      else edges.set(key, { a: ring[i], b: ring[i + 1], count: 1 });
    }
  };
  for (const feature of departements.features) {
    const geometry = feature.geometry;
    const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    for (const polygon of polygons) for (const ring of polygon) visit(ring);
  }

  const adjacency = new Map<string, { key: string; a: Position; b: Position }[]>();
  const boundary: { key: string; a: Position; b: Position }[] = [];
  edges.forEach(({ a, b, count }, key) => {
    if (count !== 1) return;
    const edge = { key, a, b };
    boundary.push(edge);
    for (const endpoint of [keyOf(a), keyOf(b)]) {
      const list = adjacency.get(endpoint);
      if (list) list.push(edge);
      else adjacency.set(endpoint, [edge]);
    }
  });

  // Boundary edges form closed rings — walking forward from any edge loops
  // back to its start, so extending only the tail is enough.
  const used = new Set<string>();
  const lines: Position[][] = [];
  for (const start of boundary) {
    if (used.has(start.key)) continue;
    used.add(start.key);
    const line: Position[] = [start.a, start.b];
    let extended = true;
    while (extended) {
      extended = false;
      const tailKey = keyOf(line[line.length - 1]);
      for (const candidate of adjacency.get(tailKey) ?? []) {
        if (used.has(candidate.key)) continue;
        used.add(candidate.key);
        line.push(keyOf(candidate.a) === tailKey ? candidate.b : candidate.a);
        extended = true;
        break;
      }
    }
    lines.push(line);
  }
  return lines;
}

/** Load the department index (bbox + name) generated by scripts/build-communes-geo.mjs. */
export async function loadDeptIndex(): Promise<Record<string, DeptIndexEntry>> {
  const res = await fetch(`${GEO_BASE}/index.json`);
  if (!res.ok) throw new Error(`Failed to load commune index (HTTP ${res.status})`);
  return res.json() as Promise<Record<string, DeptIndexEntry>>;
}

/**
 * Load one department's commune contours and precompute per-feature bboxes.
 * `hd` picks the 100m-simplified variant (metropolitan departments only)
 * used for detailed rendering at high zoom; the default 1000m variant is
 * light enough to load for the whole country up front.
 */
export async function loadDeptCommunes(dept: string, hd = false): Promise<CommuneFeature[]> {
  const res = await fetch(`${hd ? GEO_HD_BASE : GEO_BASE}/${dept}.geojson`);
  if (!res.ok) throw new Error(`Failed to load communes for dept ${dept} (HTTP ${res.status})`);
  const collection = (await res.json()) as { features: CommuneGeometry[] };
  return collection.features.map((feature) => ({
    code: feature.properties.code,
    nom: feature.properties.nom,
    pop: feature.properties.pop ?? 0,
    dept,
    bbox: computeBbox(feature.geometry.coordinates),
    feature,
  }));
}

export function bboxContains(bbox: Bbox, lng: number, lat: number): boolean {
  return lng >= bbox[0] && lat >= bbox[1] && lng <= bbox[2] && lat <= bbox[3];
}

export function bboxIntersects(a: Bbox, b: Bbox): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

const METERS_PER_DEGREE_LAT = 111_320;

/**
 * True when the commune polygon intersects a circular brush.
 *
 * The exact test is approximated by: circle center inside the polygon, or any
 * polygon vertex within the radius. With 1000m-simplified contours (vertices
 * every ~1 km) and brush radii of several km this misses nothing in practice,
 * and stays cheap enough to run on every mousemove.
 */
export function communeIntersectsCircle(
  commune: CommuneFeature,
  lng: number,
  lat: number,
  radiusMeters: number,
): boolean {
  const cosLat = Math.cos((lat * Math.PI) / 180);
  const latMargin = radiusMeters / METERS_PER_DEGREE_LAT;
  const lngMargin = radiusMeters / (METERS_PER_DEGREE_LAT * Math.max(cosLat, 0.01));
  const [w, s, e, n] = commune.bbox;
  if (lng < w - lngMargin || lat < s - latMargin || lng > e + lngMargin || lat > n + latMargin) {
    return false;
  }
  if (booleanPointInPolygon([lng, lat], commune.feature)) return true;
  return anyVertexWithin(
    commune.feature.geometry.coordinates,
    lng,
    lat,
    radiusMeters * radiusMeters,
    cosLat,
  );
}

/* Equirectangular distance — accurate enough at brush scale, no trig per vertex. */
function anyVertexWithin(
  coords: Coords,
  lng: number,
  lat: number,
  radiusSqMeters: number,
  cosLat: number,
): boolean {
  if (typeof coords[0] === "number") {
    const [vLng, vLat] = coords as Position;
    const dx = (vLng - lng) * cosLat * METERS_PER_DEGREE_LAT;
    const dy = (vLat - lat) * METERS_PER_DEGREE_LAT;
    return dx * dx + dy * dy <= radiusSqMeters;
  }
  for (const c of coords as Coords[]) {
    if (anyVertexWithin(c, lng, lat, radiusSqMeters, cosLat)) return true;
  }
  return false;
}

type Coords = Position | Coords[];

function computeBbox(coords: Coords): Bbox {
  const bbox: Bbox = [Infinity, Infinity, -Infinity, -Infinity];
  extend(bbox, coords);
  return bbox;
}

function extend(bbox: Bbox, coords: Coords): void {
  if (typeof coords[0] === "number") {
    const [lng, lat] = coords as Position;
    bbox[0] = Math.min(bbox[0], lng);
    bbox[1] = Math.min(bbox[1], lat);
    bbox[2] = Math.max(bbox[2], lng);
    bbox[3] = Math.max(bbox[3], lat);
    return;
  }
  for (const c of coords as Coords[]) extend(bbox, c);
}
