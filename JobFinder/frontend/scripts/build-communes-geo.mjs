/**
 * Build the per-department commune contour files used by CommuneZonePicker.
 *
 * Source (licence ouverte / Etalab): contours-administratifs 2024. Two
 * simplification levels are used: 1000m for the always-loaded painting
 * dataset, and 100m for the high-detail contours fetched lazily when the map
 * is zoomed in. The dataset already includes the municipal arrondissements
 * of Paris/Lyon/Marseille — only the three parent communes are dropped,
 * because France Travail offers carry arrondissement-level INSEE codes
 * (e.g. 75101), never the parent commune code (75056).
 *
 * Each feature carries the commune population (geo.api.gouv.fr) so the map
 * can reveal town labels progressively by size while zooming.
 *
 * Output:
 *   public/geo/communes/<dept>.geojson     — 1000m FeatureCollection per department
 *   public/geo/communes-hd/<dept>.geojson  — 100m FeatureCollection (metropolitan only)
 *   public/geo/communes/index.json         — department code -> { bbox: [W,S,E,N], nom }
 *   public/geo/departements.geojson        — department contours (stylised basemap)
 *
 * Usage: node scripts/build-communes-geo.mjs
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const COMMUNES_URL =
  "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2024/geojson/communes-1000m.geojson";
const COMMUNES_HD_URL =
  "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2024/geojson/communes-100m.geojson";
const DEPARTEMENTS_URL =
  "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2024/geojson/departements-1000m.geojson";
const POPULATION_URLS = [
  "https://geo.api.gouv.fr/communes?fields=code,population",
  "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=code,population",
];

// Parent communes whose municipal arrondissements are already in the dataset.
const PLM_PARENT_CODES = new Set(["75056", "69123", "13055"]);

const OUT_DIR = path.join(import.meta.dirname, "..", "public", "geo", "communes");
const OUT_HD_DIR = path.join(import.meta.dirname, "..", "public", "geo", "communes-hd");

async function fetchJson(url) {
  console.log(`Downloading ${url}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

/** Extend [W, S, E, N] bbox in place with every position of a geometry. */
function extendBbox(bbox, coords) {
  if (typeof coords[0] === "number") {
    const [lng, lat] = coords;
    bbox[0] = Math.min(bbox[0], lng);
    bbox[1] = Math.min(bbox[1], lat);
    bbox[2] = Math.max(bbox[2], lng);
    bbox[3] = Math.max(bbox[3], lat);
    return;
  }
  for (const c of coords) extendBbox(bbox, c);
}

/** Round every position to 4 decimals (~11m) — halves the 100m file weight. */
function roundCoords(coords) {
  if (typeof coords[0] === "number") {
    return [Math.round(coords[0] * 1e4) / 1e4, Math.round(coords[1] * 1e4) / 1e4];
  }
  return coords.map(roundCoords);
}

/** Drop PLM parents and duplicated codes, keep only the needed properties. */
function cleanCommunes(collection, popByCode) {
  const seenCodes = new Set();
  return collection.features
    .filter((f) => !PLM_PARENT_CODES.has(f.properties.code))
    .filter((f) => {
      if (seenCodes.has(f.properties.code)) return false;
      seenCodes.add(f.properties.code);
      return true;
    })
    .map((f) => ({
      type: "Feature",
      properties: {
        code: f.properties.code,
        nom: f.properties.nom,
        pop: popByCode.get(f.properties.code) ?? 0,
        dept: f.properties.departement,
      },
      geometry: f.geometry,
    }));
}

function groupByDept(features) {
  const byDept = new Map();
  for (const f of features) {
    const dept = f.properties.dept;
    if (!byDept.has(dept)) byDept.set(dept, []);
    byDept.get(dept).push(f);
  }
  return byDept;
}

async function writeDeptFiles(byDept, outDir, { roundGeometry = false } = {}) {
  await mkdir(outDir, { recursive: true });
  for (const [dept, deptFeatures] of [...byDept.entries()].sort()) {
    const collection = {
      type: "FeatureCollection",
      features: deptFeatures.map((f) => ({
        type: "Feature",
        properties: { code: f.properties.code, nom: f.properties.nom, pop: f.properties.pop },
        geometry: roundGeometry
          ? { type: f.geometry.type, coordinates: roundCoords(f.geometry.coordinates) }
          : f.geometry,
      })),
    };
    await writeFile(path.join(outDir, `${dept}.geojson`), JSON.stringify(collection));
    console.log(`${path.basename(outDir)}/${dept}: ${deptFeatures.length} communes`);
  }
}

async function main() {
  const [communes, communesHd, departements, ...populations] = await Promise.all([
    fetchJson(COMMUNES_URL),
    fetchJson(COMMUNES_HD_URL),
    fetchJson(DEPARTEMENTS_URL),
    ...POPULATION_URLS.map(fetchJson),
  ]);

  const popByCode = new Map();
  for (const list of populations) {
    for (const { code, population } of list) {
      if (typeof population === "number") popByCode.set(code, population);
    }
  }
  console.log(`populations: ${popByCode.size} codes`);

  await mkdir(path.join(OUT_DIR, ".."), { recursive: true });
  await writeFile(
    path.join(OUT_DIR, "..", "departements.geojson"),
    JSON.stringify({
      type: "FeatureCollection",
      features: departements.features.map((f) => ({
        type: "Feature",
        properties: { code: f.properties.code, nom: f.properties.nom },
        geometry: f.geometry,
      })),
    }),
  );
  console.log(`departements: ${departements.features.length} features`);

  const byDept = groupByDept(cleanCommunes(communes, popByCode));

  const deptNoms = new Map(
    departements.features.map((f) => [f.properties.code, f.properties.nom]),
  );
  const index = {};
  for (const [dept, deptFeatures] of [...byDept.entries()].sort()) {
    const bbox = [Infinity, Infinity, -Infinity, -Infinity];
    for (const f of deptFeatures) extendBbox(bbox, f.geometry.coordinates);
    index[dept] = {
      bbox: bbox.map((v) => Math.round(v * 1e4) / 1e4),
      nom: deptNoms.get(dept) ?? dept,
    };
  }
  await writeDeptFiles(byDept, OUT_DIR);
  await writeFile(path.join(OUT_DIR, "index.json"), JSON.stringify(index));

  // High-detail set: the map is locked on metropolitan France, overseas
  // departments and collectivities can never be zoomed into — skip them to
  // keep the repo lean.
  const byDeptHd = groupByDept(cleanCommunes(communesHd, popByCode));
  for (const dept of [...byDeptHd.keys()]) {
    if (/^9[78]/.test(dept)) byDeptHd.delete(dept);
  }
  await writeDeptFiles(byDeptHd, OUT_HD_DIR, { roundGeometry: true });

  console.log(`Done — ${byDept.size} departments (${byDeptHd.size} in HD).`);
}

await main();
