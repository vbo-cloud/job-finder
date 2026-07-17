"use client";

import { cn } from "@/lib/utils";

interface ExperienceToggleProps {
  value: "0-2" | "2-5" | "5+" | null;
  onChange: (value: "0-2" | "2-5" | "5+" | null) => void;
}

const OPTIONS: { value: "0-2" | "2-5" | "5+"; label: string; sub: string }[] = [
  { value: "0-2", label: "Junior", sub: "0 à 2 ans" },
  { value: "2-5", label: "Confirmé", sub: "2 à 5 ans" },
  { value: "5+", label: "Senior", sub: "5 ans et +" },
];

export default function ExperienceToggle({ value, onChange }: ExperienceToggleProps) {
  return (
    // Stacked below sm: three side-by-side options get too narrow for their
    // label + sub-label on a 375px screen once the page paddings are deducted.
    <div className="flex flex-col gap-2 sm:flex-row">
      {OPTIONS.map((option) => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(isActive ? null : option.value)}
            className={cn(
              "flex flex-1 flex-col items-start gap-0.5 rounded-xl border px-3.5 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              isActive
                ? "border-accent bg-accent-muted text-accent"
                : "border-profile bg-profile-surface text-body hover:bg-card-hover",
            )}
          >
            <span className="text-sm font-semibold">{option.label}</span>
            <span className="text-[11px] opacity-70">{option.sub}</span>
          </button>
        );
      })}
    </div>
  );
}
