"use client";

import { useEffect, useState } from "react";

/**
 * True when the device has at least one coarse pointer (touch screen).
 * `any-pointer` rather than `pointer`: a touch-capable laptop whose primary
 * pointer is the trackpad must still expose the touch affordances.
 * Starts false (SSR and first client render agree — no hydration mismatch)
 * and resolves after mount; also false under jsdom, where matchMedia is absent.
 */
export default function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(any-pointer: coarse)");
    const update = () => setCoarse(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return coarse;
}
