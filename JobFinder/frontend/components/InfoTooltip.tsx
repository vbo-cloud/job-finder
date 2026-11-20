"use client";

import { useId, useState } from "react";

interface InfoTooltipProps {
  text: string;
}

export function InfoTooltip({ text }: InfoTooltipProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = useId();

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Plus d'informations"
        aria-describedby={tooltipId}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        className="flex h-4 w-4 items-center justify-center rounded-full border border-default text-[10px] text-muted transition-colors hover:border-hover hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        ?
      </button>
      {visible && (
        <span
          id={tooltipId}
          role="tooltip"
          // Below md the desktop placement (left-full, 224px wide) would spill
          // past the right edge of a phone viewport and create horizontal
          // scroll — centre a narrower bubble on the icon instead. A touch tap
          // focuses the button, so onFocus keeps the tooltip reachable there.
          className="absolute bottom-full left-1/2 z-10 w-48 -translate-x-1/2 rounded border border-default bg-surface px-2 py-1.5 text-xs text-body shadow-lg md:left-full md:w-56 md:translate-x-0"
        >
          {text}
        </span>
      )}
    </span>
  );
}
