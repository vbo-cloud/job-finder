import { cn } from "@/lib/utils";

export interface AnalysisPoint {
  text: string;
  /** Secondary line rendered with the "suggestion" bullet; no line when null/absent. */
  suggestion?: string | null;
}

interface Props {
  title: string;
  items: (string | AnalysisPoint)[];
  variant: "positive" | "negative" | "suggestion";
}

const BULLETS = {
  positive: { char: "✓", className: "text-success" },
  negative: { char: "•", className: "text-destructive" },
  suggestion: { char: "→", className: "text-accent" },
} as const;

/** Titled bullet list shared by the CV quality card and the match analysis panel. */
export default function AnalysisPointsList({ title, items, variant }: Props) {
  if (items.length === 0) return null;
  const bullet = BULLETS[variant];
  return (
    <div>
      <p className="text-[10.5px] font-bold tracking-[.09em] uppercase text-muted mb-2">{title}</p>
      <ul className="flex flex-col gap-[7px] text-[13px] text-body leading-relaxed">
        {items.map((item) => {
          const point = typeof item === "string" ? { text: item } : item;
          return (
            <li key={point.text} className="flex flex-col gap-[3px]">
              <div className="flex gap-[9px]">
                <span className={cn("flex-none pt-px font-bold", bullet.className)}>{bullet.char}</span>
                <span>{point.text}</span>
              </div>
              {point.suggestion && (
                <div className="flex gap-[9px] pl-[18px]">
                  <span className={cn("flex-none pt-px font-bold", BULLETS.suggestion.className)}>
                    {BULLETS.suggestion.char}
                  </span>
                  <span>{point.suggestion}</span>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
