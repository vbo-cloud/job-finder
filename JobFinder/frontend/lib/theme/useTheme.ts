"use client";

import { useEffect, useState } from "react";

import { applyTheme } from "./index";
import { darkTheme } from "./themes/dark";
import { lightTheme } from "./themes/light";

export type ThemeId = "dark" | "light";

const STORAGE_KEY = "theme";

const themes = { dark: darkTheme, light: lightTheme } as const;

export function useTheme() {
  // Start with dark to match the globals.css default (prevents icon flicker on first render)
  const [themeId, setThemeId] = useState<ThemeId>("dark");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    if (stored === "light") {
      setThemeId("light");
      applyTheme(lightTheme);
    }
  }, []);

  function toggle() {
    const next: ThemeId = themeId === "dark" ? "light" : "dark";
    setThemeId(next);
    applyTheme(themes[next]);
    localStorage.setItem(STORAGE_KEY, next);
  }

  return { themeId, toggle };
}
