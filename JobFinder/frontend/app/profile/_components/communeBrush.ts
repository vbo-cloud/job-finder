import type L from "leaflet";

import { communeIntersectsCircle, type CommuneFeature } from "./communeGeo";

/** Fixed on-screen brush radius — covers more communes the further the map is zoomed out. */
const BRUSH_RADIUS_PX = 24;

/** Grace period before the first stamp of a touch stroke. A pinch's second
 * finger virtually always lands within this window — deferring the first
 * stamp until the grace expires keeps a two-finger zoom/pan from leaving
 * paint behind (stamping on touchstart made every pinch paint a blob under
 * whichever finger landed first). A tap shorter than the grace still paints:
 * the pending stroke is committed on touchend instead. */
const TOUCH_STROKE_GRACE_MS = 120;

const EARTH_CIRCUMFERENCE_M = 40_075_016.686;

/** One-finger touch behaviour, selected in the picker's floating toolbar.
 * Two-finger gestures (pinch zoom, two-finger pan) bypass the active tool and
 * always navigate the map. Mouse interactions ignore it entirely — the
 * left/right/middle buttons keep their fixed paint/erase/pan roles. */
export type TouchTool = "paint" | "erase" | "pan";

export interface BrushOptions {
  /** Current selection — read live at stamp time (mirror of the controlled value). */
  getSelected: () => ReadonlySet<string>;
  /** Live geometry store — the caller keeps filling it as departments load. */
  communes: Map<string, CommuneFeature>;
  /** Active one-finger touch tool — read live at gesture start. */
  getTouchTool: () => TouchTool;
  /** Called once per brush stroke, before its first effective change — undo snapshot hook. */
  onStrokeStart: () => void;
  onChange: (codes: string[]) => void;
  /** True while a brush stroke is in progress (mouse button or finger down). */
  onPaintingChange: (painting: boolean) => void;
}

/**
 * Wires the brush interactions onto a Leaflet map container and returns the
 * cleanup that unwires everything. Mouse: left = paint, right = erase, middle
 * drag = pan, wheel = zoom (Leaflet's own handler). Touch: one finger runs
 * the active TouchTool, two fingers are left to Leaflet's pinch zoom (which
 * also pans with the midpoint). The circular brush cursor is a DOM overlay
 * appended to the container.
 */
export function attachBrushInteractions(map: L.Map, opts: BrushOptions): () => void {
  const container = map.getContainer();
  container.style.cursor = "crosshair";
  // One-finger gestures are fully handled below and two-finger gestures
  // belong to Leaflet — the browser must not consume any of them to scroll
  // or zoom the page instead.
  container.style.touchAction = "none";

  let stroke: "paint" | "erase" | null = null;
  let strokeSnapshotted = false;
  let panPoint: { x: number; y: number } | null = null;

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

  const positionBrush = (clientX: number, clientY: number) => {
    const rect = container.getBoundingClientRect();
    brush.style.transform =
      `translate(${clientX - rect.left - BRUSH_RADIUS_PX}px, ` +
      `${clientY - rect.top - BRUSH_RADIUS_PX}px)`;
  };

  const moveBrush = (e: MouseEvent) => {
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    // Being inside the rectangle is not enough: embedded on the home page
    // the map also lives as a non-interactive background layer
    // (pointer-events: none) — only show the brush when the cursor
    // actually reaches the map.
    const hit =
      x >= 0 && y >= 0 && x <= rect.width && y <= rect.height
        ? document.elementFromPoint(e.clientX, e.clientY)
        : null;
    const visible = hit !== null && container.contains(hit);
    brush.style.display = visible ? "block" : "none";
    positionBrush(e.clientX, e.clientY);
  };

  // The zoom-dependent factor is cached per zoom level — stamp runs on
  // every mousemove of a stroke, only the latitude term varies.
  let equatorMetersPerPixel = { zoom: NaN, value: 0 };
  const stamp = (clientX: number, clientY: number, erase: boolean) => {
    // mouseEventToLatLng only reads clientX/clientY — a bare coordinate
    // object works for both mouse events and touch points.
    const latlng = map.mouseEventToLatLng({ clientX, clientY } as MouseEvent);
    const zoom = map.getZoom();
    if (equatorMetersPerPixel.zoom !== zoom) {
      equatorMetersPerPixel = { zoom, value: EARTH_CIRCUMFERENCE_M / Math.pow(2, zoom + 8) };
    }
    const radiusM =
      BRUSH_RADIUS_PX *
      equatorMetersPerPixel.value *
      Math.abs(Math.cos((latlng.lat * Math.PI) / 180));

    const next = new Set(opts.getSelected());
    let changed = false;
    opts.communes.forEach((commune) => {
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
    if (!strokeSnapshotted) {
      strokeSnapshotted = true;
      opts.onStrokeStart();
    }
    opts.onChange(Array.from(next));
  };

  const onMouseDown = (e: MouseEvent) => {
    // Clicks on Leaflet controls must not paint.
    if ((e.target as HTMLElement).closest(".leaflet-control-container")) return;
    // preventDefault() below suppresses the implicit focus — restore it so
    // Leaflet keyboard navigation (+/- and arrows) keeps working.
    container.focus({ preventScroll: true });
    if (e.button === 0) {
      stroke = "paint";
      strokeSnapshotted = false;
      setBrushAppearance(false);
      opts.onPaintingChange(true);
      stamp(e.clientX, e.clientY, false);
      e.preventDefault();
    } else if (e.button === 2) {
      stroke = "erase";
      strokeSnapshotted = false;
      setBrushAppearance(true);
      opts.onPaintingChange(true);
      stamp(e.clientX, e.clientY, true);
      e.preventDefault();
    } else if (e.button === 1) {
      panPoint = { x: e.clientX, y: e.clientY };
      e.preventDefault(); // suppress browser autoscroll
    }
  };
  const onMouseMove = (e: MouseEvent) => {
    moveBrush(e);
    if (panPoint) {
      map.panBy([panPoint.x - e.clientX, panPoint.y - e.clientY], { animate: false });
      panPoint = { x: e.clientX, y: e.clientY };
      return;
    }
    if (stroke) stamp(e.clientX, e.clientY, stroke === "erase");
  };
  const onMouseUp = () => {
    stroke = null;
    panPoint = null;
    setBrushAppearance(false);
    opts.onPaintingChange(false);
  };
  const onContextMenu = (e: MouseEvent) => e.preventDefault();
  const onMouseLeave = () => {
    brush.style.display = "none";
  };

  // Touch: one finger runs the active tool, a second finger aborts the
  // one-finger gesture and hands over to Leaflet's pinch zoom — map
  // navigation never requires switching tool. preventDefault() on the
  // one-finger path suppresses the browser's simulated mouse events:
  // without it a tap would re-enter onMouseDown and paint whatever the
  // active tool is.
  //
  // Paint/erase strokes do not start on touchstart: they sit pending for
  // TOUCH_STROKE_GRACE_MS (path accumulated, brush visible, nothing painted)
  // and only commit once the grace expires — or on touchend for a quick tap.
  // A second finger landing during the grace cancels the pending stroke
  // outright, so a pinch never paints.
  let pendingTouch: {
    erase: boolean;
    points: { x: number; y: number }[];
    timer: ReturnType<typeof setTimeout>;
  } | null = null;

  const commitPendingTouch = () => {
    if (!pendingTouch) return;
    const { erase, points, timer } = pendingTouch;
    clearTimeout(timer);
    pendingTouch = null;
    stroke = erase ? "erase" : "paint";
    strokeSnapshotted = false;
    opts.onPaintingChange(true);
    // Replay the path accumulated during the grace — the stroke starts where
    // the finger landed, not where it happens to be when the grace expires.
    for (const point of points) stamp(point.x, point.y, erase);
  };

  const cancelPendingTouch = () => {
    if (!pendingTouch) return;
    clearTimeout(pendingTouch.timer);
    pendingTouch = null;
    brush.style.display = "none";
    setBrushAppearance(false);
  };

  const endTouchGesture = () => {
    panPoint = null;
    if (!stroke) return;
    stroke = null;
    brush.style.display = "none";
    setBrushAppearance(false);
    opts.onPaintingChange(false);
  };

  const onTouchStart = (e: TouchEvent) => {
    if ((e.target as HTMLElement).closest(".leaflet-control-container")) return;
    if (e.touches.length !== 1) {
      cancelPendingTouch();
      endTouchGesture();
      return; // no preventDefault: Leaflet's TouchZoom owns the gesture now
    }
    const touch = e.touches[0];
    if (opts.getTouchTool() === "pan") {
      panPoint = { x: touch.clientX, y: touch.clientY };
    } else {
      const erase = opts.getTouchTool() === "erase";
      setBrushAppearance(erase);
      positionBrush(touch.clientX, touch.clientY);
      brush.style.display = "block";
      pendingTouch = {
        erase,
        points: [{ x: touch.clientX, y: touch.clientY }],
        timer: setTimeout(commitPendingTouch, TOUCH_STROKE_GRACE_MS),
      };
    }
    e.preventDefault();
  };
  const onTouchMove = (e: TouchEvent) => {
    if (e.touches.length !== 1) return; // pinch in progress — Leaflet's business
    const touch = e.touches[0];
    if (panPoint) {
      map.panBy([panPoint.x - touch.clientX, panPoint.y - touch.clientY], { animate: false });
      panPoint = { x: touch.clientX, y: touch.clientY };
      e.preventDefault();
    } else if (pendingTouch) {
      positionBrush(touch.clientX, touch.clientY);
      pendingTouch.points.push({ x: touch.clientX, y: touch.clientY });
      e.preventDefault();
    } else if (stroke) {
      positionBrush(touch.clientX, touch.clientY);
      stamp(touch.clientX, touch.clientY, stroke === "erase");
      e.preventDefault();
    }
  };
  const onTouchEnd = (e: TouchEvent) => {
    if (e.touches.length !== 0) return;
    // Going from two fingers to one leaves the tail of the pinch to
    // Leaflet; a new one-finger gesture starts from a fresh touchstart.
    // A tap released within the grace still paints: commit now.
    commitPendingTouch();
    endTouchGesture();
  };
  const onTouchCancel = () => {
    cancelPendingTouch();
    endTouchGesture();
  };

  container.addEventListener("mousedown", onMouseDown);
  container.addEventListener("contextmenu", onContextMenu);
  container.addEventListener("mouseleave", onMouseLeave);
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
  // Non-passive: both single-finger paths call preventDefault().
  container.addEventListener("touchstart", onTouchStart, { passive: false });
  container.addEventListener("touchmove", onTouchMove, { passive: false });
  container.addEventListener("touchend", onTouchEnd);
  container.addEventListener("touchcancel", onTouchCancel);
  return () => {
    cancelPendingTouch();
    container.removeEventListener("mousedown", onMouseDown);
    container.removeEventListener("contextmenu", onContextMenu);
    container.removeEventListener("mouseleave", onMouseLeave);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
    container.removeEventListener("touchstart", onTouchStart);
    container.removeEventListener("touchmove", onTouchMove);
    container.removeEventListener("touchend", onTouchEnd);
    container.removeEventListener("touchcancel", onTouchCancel);
    brush.remove();
    container.style.cursor = "";
    container.style.touchAction = "";
  };
}
