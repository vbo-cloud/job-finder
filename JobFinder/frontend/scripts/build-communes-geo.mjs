/**
 * Build the per-department commune contour files used by CommuneZonePicker.
 *
 * Sources (licence ouverte / Etalab):
 *   - Communes:  contours-administratifs 2024, simplification 1000m
 *   - Arrondissements municipaux (Paris/Lyon/Marseille): geo.api.gouv.fr
 *
 * Paris, Lyon and Marseille are replaced by their municipal arrondissements
 * because France Travail offers carry arrondissement-level INSEE codes
 * (e.g. 75101), never the parent commune code (75056).
 *
 * Output:
 *   public/geo/communes/<dept>.geojson  — one FeatureCollection per department
 *   public/geo/communes/index.json     — department code -> [W, S, E, N] bbox
 *
 * Usage: node scripts/build-communes-geo.mjs
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const COMMUNES_URL =
  "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2024/geojson/communes-1000m.geojson";
const ARRONDISSEMENTS_URL =
  "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&format=geojson&geometry=contour";

// Parent communes replaced by their municipal arrondissements.
const PLM_PARENT_CODES = new Set(["75056", "69123", "13055"]);

const OUT_DIR = path.join(import.meta.dirname, "..", "public", "geo", "communes");

async function fetchGeoJson(url) {
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

async function main() {
  const [communes, arrondissements] = await Promise.all([
    fetchGeoJson(COMMUNES_URL),
    fetchGeoJson(ARRONDISSEMENTS_URL),
  ]);

  const features = [
    ...communes.features
      .filter((f) => !PLM_PARENT_CODES.has(f.properties.code))
      .map((f) => ({
        type: "Feature",
        properties: {
          code: f.properties.code,
          nom: f.properties.nom,
          dept: f.properties.departement,
        },
        geometry: f.geometry,
      })),
    ...arrondissements.features.map((f) => ({
      type: "Feature",
      properties: {
        code: f.properties.code,
        nom: f.properties.nom,
        dept: f.properties.codeDepartement,
      },
      geometry: f.geometry,
    })),
  ];

  const byDept = new Map();
  for (const f of features) {
    const dept = f.properties.dept;
    if (!byDept.has(dept)) byDept.set(dept, []);
    byDept.get(dept).push(f);
  }

  await mkdir(OUT_DIR, { recursive: true });

  const index = {};
  for (const [dept, deptFeatures] of [...byDept.entries()].sort()) {
    const bbox = [Infinity, Infinity, -Infinity, -Infinity];
    for (const f of deptFeatures) extendBbox(bbox, f.geometry.coordinates);
    index[dept] = bbox.map((v) => Math.round(v * 1e4) / 1e4);

    const collection = {
      type: "FeatureCollection",
      features: deptFeatures.map((f) => ({
        type: "Feature",
        properties: { code: f.properties.code, nom: f.properties.nom },
        geometry: f.geometry,
      })),
    };
    await writeFile(path.join(OUT_DIR, `${dept}.geojson`), JSON.stringify(collection));
    console.log(`${dept}: ${deptFeatures.length} communes`);
  }

  await writeFile(path.join(OUT_DIR, "index.json"), JSON.stringify(index));
  console.log(`Done — ${byDept.size} departments, ${features.length} communes.`);
}

await main();
