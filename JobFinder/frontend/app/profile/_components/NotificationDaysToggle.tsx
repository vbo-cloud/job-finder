"use client";

import { cn } from "@/lib/utils";

interface NotificationDaysToggleProps {
  value: number[];
  onChange: (value: number[]) => void;
}

const DAYS: { value: number; label: string }[] = [
  { value: 1, label: "Lun" },
  { value: 2, label: "Mar" },
  { value: 3, label: "Mer" },
  { value: 4, label: "Jeu" },
  { value: 5, label: "Ven" },
  { value: 6, label: "Sam" },
  { value: 7, label: "Dim" },
];

export default function NotificationDaysToggle({ value, onChange }: NotificationDaysToggleProps) {
  function toggleDay(day: number) {
    onChange(value.includes(day) ? value.filter((d) => d !== day) : [...value, day].sort());
  }

  return (
    <div
      role="group"
      aria-label="Jours de notification"
      className="grid grid-cols-4 gap-2 sm:grid-cols-7"
    >
      {DAYS.map((day) => {
        const isActive = value.includes(day.value);
        return (
          <button
            key={day.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => toggleDay(day.value)}
            className={cn(
              "flex flex-col items-center gap-0.5 rounded-xl border px-2 py-2.5 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              isActive
                ? "border-accent bg-accent-muted text-accent"
                : "border-profile bg-profile-surface text-body hover:bg-card-hover",
            )}
          >
            <span className="text-sm font-semibold">{day.label}</span>
          </button>
        );
      })}
    </div>
  );
}
