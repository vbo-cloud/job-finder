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
          className="absolute bottom-full left-full z-10 w-56 rounded border border-default bg-surface px-2 py-1.5 text-xs text-body shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  );
}
