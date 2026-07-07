"use client";

import { useIsAuthenticated } from "@azure/msal-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
  type CSSProperties,
} from "react";

import apiClient from "@/lib/api/client";
import type { ProfileData } from "@/lib/api/types";

import MapSection from "./MapSection";
import UploadSection from "./UploadSection";

type Mode = "cv" | "to-map" | "map" | "to-cv";

/** Duration of the camera focus-pull — single source of truth for the mode
 * timers, the CSS layer transitions and the lens keyframe animation below. */
const TRANSITION_MS = 425;

/** Delay before auto-saving the painted zone to the profile (flushed
 * immediately when leaving the map mode). */
const SAVE_DEBOUNCE_MS = 800;

/** Scrolling down over the map exits the map mode only once the view has
 * been fully zoomed out for this long — the grace period keeps the wheel
 * momentum of the final zoom-out from overshooting into an exit. Tuned by
 * hand: the trailing wheel ticks of a fast zoom-out land within well under
 * 200ms of the settling zoomend, while a deliberate second scroll takes
 * longer than that — raise/lower with that trade-off in mind. */
const MIN_ZOOM_EXIT_HOLD_MS = 200;

/** Light blur only on the backgrounded map: its borders must stay readable
 * behind the CV layer. The CV layer can afford a strong defocus. */
const MAP_BLUR = "blur(4px)";
const CV_BLUR = "blur(14px)";

const LAYER_TRANSITION = ["filter", "opacity", "transform"]
  .map((prop) => `${prop} ${TRANSITION_MS}ms ease-in-out`)
  .join(", ");

/* The layer styles are target values only: switching mode changes the
 * targets and the CSS transitions animate towards them. Both layers stay
 * mounted and laid out in every mode (opacity/filter/transform only — never
 * display/visibility/unmount, which would break Leaflet's size handling). */

function cvLayerStyle(mode: Mode): CSSProperties {
  const focused = mode === "cv" || mode === "to-cv";
  return {
    transition: LAYER_TRANSITION,
    filter: focused ? "none" : CV_BLUR,
    opacity: focused ? 1 : 0,
    transform: focused ? "scale(1)" : "scale(1.12)",
    // "to-cv" keeps pointer-events off until the transition has fully landed.
    pointerEvents: mode === "cv" ? "auto" : "none",
  };
}

function mapLayerStyle(mode: Mode): CSSProperties {
  const focused = mode === "map" || mode === "to-map";
  return {
    transition: LAYER_TRANSITION,
    filter: focused ? "none" : MAP_BLUR,
    // Never 0 outside the map mode: the map stays visible, centred and
    // blurred, behind the CV layer at all times. Scaling around the centre
    // keeps the map seated at the same spot in both modes — the offset that
    // seats France on the CV icon lives in the embedded MapContainer
    // geometry (CommuneZonePicker), not in this transform.
    opacity: focused ? 1 : 0.3,
    transform: focused ? "scale(1)" : "scale(0.94)",
    pointerEvents: mode === "map" ? "auto" : "none",
  };
}

const LENS_BACKGROUND =
  "radial-gradient(ellipse at center, transparent 55%, var(--bg-scrim) 100%)";

/** Decorative vignette flashing in and out during the transitions —
 * lensPulse (globals.css) animates opacity 0 → peak → 0. */
function lensStyle(mode: Mode): CSSProperties {
  return {
    pointerEvents: "none",
    opacity: 0,
    background: LENS_BACKGROUND,
    animation:
      mode === "to-map" || mode === "to-cv"
        ? `lensPulse ${TRANSITION_MS}ms ease-in-out`
        : "none",
  };
}

interface HomeMapSectionProps {
  uploadProps: ComponentProps<typeof UploadSection>;
  /** Called after the painted zone is successfully persisted to the
   * profile — lets the parent invalidate anything derived from it (e.g.
   * the matches list, which stays mounted and won't refetch on its own). */
  onZoneSaved?: () => void;
}

/**
 * Home hero section holding two stacked layers: the CV upload screen
 * (UploadSection) and the commune map (MapSection) behind it, blurred.
 * Scrolling up from the CV layer (signed in only — the zone lives on the
 * profile) triggers a camera focus-pull transition that brings the map
 * into focus and makes it paintable; scrolling down
 * from the map plays the reverse transition — either with the cursor
 * outside the Leaflet container, or over it once the view has been fully
 * zoomed out for a moment (no brush stroke in progress in both cases).
 * The painted zone is auto-saved to the profile with a debounce, flushed
 * when leaving the map mode.
 */
export default function HomeMapSection({ uploadProps, onZoneSaved }: HomeMapSectionProps) {
  const isAuthenticated = useIsAuthenticated();
  const sectionRef = useRef<HTMLElement>(null);
  const onZoneSavedRef = useRef(onZoneSaved);
  onZoneSavedRef.current = onZoneSaved;

  const [mode, setMode] = useState<Mode>("cv");
  const [communeCodes, setCommuneCodes] = useState<string[]>([]);
  // Incremented on each exit so the map snaps back to its origin view —
  // the backgrounded map must never keep a zoom or pan offset.
  const [viewResetToken, setViewResetToken] = useState(0);

  const modeRef = useRef(mode);
  modeRef.current = mode;
  const isAuthenticatedRef = useRef(isAuthenticated);
  isAuthenticatedRef.current = isAuthenticated;

  // Refs, not state: painting and dirtiness must not re-render the layers.
  const paintingRef = useRef(false);
  // Timestamp of when the map reached its minimum zoom, null while zoomed in.
  const atMinZoomSinceRef = useRef<number | null>(null);
  const communeCodesRef = useRef<string[]>([]);
  const dirtyRef = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const modeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initial zone load — same pattern as /profile (404 = no profile yet).
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    apiClient
      .get<ProfileData>("/profile")
      .then((res) => {
        if (cancelled) return;
        const codes = res.data.commune_codes ?? [];
        setCommuneCodes(codes);
        communeCodesRef.current = codes;
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 404) return;
        console.error("[home] GET /profile failed:", err);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  const flushSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    if (!dirtyRef.current || !isAuthenticatedRef.current) return;
    dirtyRef.current = false;
    apiClient
      .put("/profile", { commune_codes: communeCodesRef.current })
      .then(() => onZoneSavedRef.current?.())
      .catch((err: unknown) => console.error("[home] PUT /profile failed:", err));
  }, []);

  const handleZoneChange = useCallback(
    (codes: string[]) => {
      setCommuneCodes(codes);
      communeCodesRef.current = codes;
      dirtyRef.current = true;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(flushSave, SAVE_DEBOUNCE_MS);
    },
    [flushSave],
  );

  const handlePaintingChange = useCallback((painting: boolean) => {
    paintingRef.current = painting;
  }, []);

  const handleAtMinZoomChange = useCallback((atMinZoom: boolean) => {
    atMinZoomSinceRef.current = atMinZoom ? performance.now() : null;
  }, []);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const startTransition = (transition: Mode, target: Mode) => {
      setMode(transition);
      modeTimerRef.current = setTimeout(() => setMode(target), TRANSITION_MS);
    };

    const exitMap = () => {
      flushSave(); // do not lose the last stroke to the debounce
      setViewResetToken((t) => t + 1); // origin view snaps behind the exit blur
      startTransition("to-cv", "cv");
    };

    // Native non-passive listener: React attaches onWheel as passive, which
    // would silently ignore preventDefault(). Capture phase, because
    // Leaflet's ScrollWheelZoom handler stops propagation of every wheel
    // over its container — a bubble listener would never see those. Events
    // over the map are still left to Leaflet (zoom), except a scroll down
    // once the view has been fully zoomed out for a while: that one exits.
    // TODO(a11y): an Escape shortcut out of the map mode would fit here.
    const onWheel = (e: WheelEvent) => {
      const mode = modeRef.current;
      if (mode === "to-map" || mode === "to-cv") {
        e.preventDefault();
        return;
      }
      if (mode === "cv") {
        // The map mode is gated behind authentication — the zone is loaded
        // from and saved to the profile, which requires being signed in.
        if (e.deltaY < 0 && isAuthenticatedRef.current) {
          e.preventDefault();
          startTransition("to-map", "map");
        }
        return;
      }
      // mode === "map" — a brush stroke in progress absorbs the scroll,
      // even if the cursor drifted outside the Leaflet container mid-drag.
      if (paintingRef.current) return;
      const overMap =
        e.target instanceof Element && e.target.closest(".leaflet-container") !== null;
      if (overMap) {
        const since = atMinZoomSinceRef.current;
        if (
          e.deltaY > 0 &&
          since !== null &&
          performance.now() - since >= MIN_ZOOM_EXIT_HOLD_MS
        ) {
          e.preventDefault();
          e.stopPropagation(); // keep Leaflet's own wheel handler out of it
          exitMap();
        }
        return; // otherwise let Leaflet zoom
      }
      e.preventDefault();
      if (e.deltaY > 0) exitMap();
    };

    section.addEventListener("wheel", onWheel, { passive: false, capture: true });
    return () => section.removeEventListener("wheel", onWheel, { capture: true });
  }, [flushSave]);

  // Unmount: drop a pending mode timer, flush a pending save (best effort).
  useEffect(() => {
    return () => {
      if (modeTimerRef.current) clearTimeout(modeTimerRef.current);
      flushSave();
    };
  }, [flushSave]);

  return (
    <section id="home" ref={sectionRef} className="relative h-dvh snap-start overflow-hidden bg-page">
      <div className="absolute inset-0" style={cvLayerStyle(mode)}>
        <UploadSection {...uploadProps} />
      </div>
      <div className="absolute inset-0" style={mapLayerStyle(mode)}>
        <MapSection
          communeCodes={communeCodes}
          onChange={handleZoneChange}
          onPaintingChange={handlePaintingChange}
          onAtMinZoomChange={handleAtMinZoomChange}
          viewResetToken={viewResetToken}
        />
      </div>
      <div aria-hidden="true" className="absolute inset-0" style={lensStyle(mode)} />
    </section>
  );
}
