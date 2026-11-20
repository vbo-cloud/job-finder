"use client";

import { cn } from "@/lib/utils";

interface Props {
  /** Arrow direction — also decides label/arrow order: "up" shows the
   * bouncing arrow above the label, "down" shows it below. */
  direction: "up" | "down";
  label: string;
  ariaLabel: string;
  onClick?: () => void;
  /** Positioning (absolute/inset, visibility breakpoints) is the caller's
   * responsibility — every section places its hints differently. */
  className?: string;
}

/** Bouncing-arrow navigation hint shared by the home/library/detail
 * sections — a small clickable [label + animate-bounce arrow] that scrolls
 * to or reveals a sibling section. */
export default function ScrollHint({ direction, label, ariaLabel, onClick, className }: Props) {
  const arrow = (
    <span aria-hidden="true" className="animate-bounce text-sm text-hint">
      {direction === "up" ? "⌃" : "⌄"}
    </span>
  );

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={cn(
        "flex flex-col items-center gap-1 bg-transparent border-0 p-0 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
        className,
      )}
    >
      {direction === "up" && arrow}
      <span className="text-[9px] tracking-widest text-label">{label}</span>
      {direction === "down" && arrow}
    </button>
  );
}
