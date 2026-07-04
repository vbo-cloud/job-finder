import type { FeatureCollection, MultiPolygon, Polygon, Position } from "geojson";

import {
  buildFranceOutline,
  communeIntersectsCircle,
  compressSelection,
  DEPT_TOKEN_PREFIX,
  expandSelection,
  type CommuneFeature,
  type SelectableCommune,
} from "@/app/profile/_components/communeGeo";

function makeReferential(byDept: Record<string, string[]>) {
  const communeByCode = new Map<string, SelectableCommune>();
  const codesByDept = new Map<string, string[]>();
  const deptTotals = new Map<string, number>();
  for (const [dept, codes] of Object.entries(byDept)) {
    codesByDept.set(dept, codes);
    deptTotals.set(dept, codes.length);
    for (const code of codes) {
      communeByCode.set(code, { code, nom: `Commune ${code}`, dept });
    }
  }
  return { communeByCode, codesByDept, deptTotals };
}

describe("compressSelection", () => {
  const { communeByCode, deptTotals } = makeReferential({
    "74": ["74001", "74002", "74003"],
    "75": ["75101", "75102"],
  });

  it("collapses a fully selected department into its token", () => {
    const out = compressSelection(["74001", "74002", "74003"], communeByCode, deptTotals);
    expect(out).toEqual([`${DEPT_TOKEN_PREFIX}74`]);
  });

  it("keeps plain codes for a partially selected department", () => {
    const out = compressSelection(["74001", "74002"], communeByCode, deptTotals);
    expect(out.sort()).toEqual(["74001", "74002"]);
  });

  it("passes codes missing from the referential through untouched", () => {
    const out = compressSelection(["99999"], communeByCode, deptTotals);
    expect(out).toEqual(["99999"]);
  });

  it("mixes tokens and codes across departments", () => {
    const out = compressSelection(["75101", "74001", "74002", "74003"], communeByCode, deptTotals);
    expect(out.sort()).toEqual(["75101", `${DEPT_TOKEN_PREFIX}74`]);
  });
});

describe("expandSelection", () => {
  const { communeByCode, codesByDept, deptTotals } = makeReferential({
    "74": ["74001", "74002", "74003"],
    "75": ["75101", "75102"],
  });

  it("expands a department token into every commune code", () => {
    const { codes, unresolved } = expandSelection([`${DEPT_TOKEN_PREFIX}74`], codesByDept);
    expect(codes.sort()).toEqual(["74001", "74002", "74003"]);
    expect(unresolved).toEqual([]);
  });

  it("keeps tokens of departments not in the referential as unresolved", () => {
    const { codes, unresolved } = expandSelection(
      [`${DEPT_TOKEN_PREFIX}2A`, "75101"],
      codesByDept,
    );
    expect(codes).toEqual(["75101"]);
    expect(unresolved).toEqual([`${DEPT_TOKEN_PREFIX}2A`]);
  });

  it("round-trips through compressSelection", () => {
    const initial = ["74001", "74002", "74003", "75102"];
    const stored = compressSelection(initial, communeByCode, deptTotals);
    const { codes } = expandSelection(stored, codesByDept);
    expect(codes.sort()).toEqual(initial.sort());
  });
});

describe("buildFranceOutline", () => {
  it("dissolves the shared border of two adjacent squares into one outer ring", () => {
    const square = (x0: number): Position[][] => [
      [
        [x0, 0],
        [x0 + 1, 0],
        [x0 + 1, 1],
        [x0, 1],
        [x0, 0],
      ],
    ];
    const departements: FeatureCollection<Polygon | MultiPolygon, { code: string; nom: string }> =
      {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { code: "01", nom: "A" },
            geometry: { type: "Polygon", coordinates: square(0) },
          },
          {
            type: "Feature",
            properties: { code: "02", nom: "B" },
            geometry: { type: "Polygon", coordinates: square(1) },
          },
        ],
      };

    const lines = buildFranceOutline(departements);

    // The shared edge (1,0)-(1,1) appears twice and cancels out: the six
    // remaining boundary edges chain into a single closed ring.
    expect(lines).toHaveLength(1);
    expect(lines[0]).toHaveLength(7);
    expect(lines[0][0]).toEqual(lines[0][6]);
    const keys = new Set(lines[0].map(([lng, lat]) => `${lng},${lat}`));
    expect(keys.size).toBe(6);
  });
});

describe("communeIntersectsCircle", () => {
  const commune: CommuneFeature = {
    code: "74001",
    nom: "Test",
    pop: 0,
    dept: "74",
    bbox: [6.0, 46.0, 6.1, 46.1],
    feature: {
      type: "Feature",
      properties: { code: "74001", nom: "Test", pop: 0 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [6.0, 46.0],
            [6.1, 46.0],
            [6.1, 46.1],
            [6.0, 46.1],
            [6.0, 46.0],
          ],
        ],
      },
    },
  };

  it("matches when the brush center is inside the polygon", () => {
    expect(communeIntersectsCircle(commune, 6.05, 46.05, 100)).toBe(true);
  });

  it("matches when a polygon vertex falls within the brush radius", () => {
    // ~500m west of the (6.0, 46.0) corner.
    expect(communeIntersectsCircle(commune, 5.9935, 46.0, 600)).toBe(true);
  });

  it("does not match a distant brush", () => {
    expect(communeIntersectsCircle(commune, 5.5, 45.5, 1000)).toBe(false);
  });
});
