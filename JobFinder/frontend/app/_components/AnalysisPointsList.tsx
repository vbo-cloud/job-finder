import { cn } from "@/lib/utils";

interface Props {
  title: string;
  items: string[];
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
        {items.map((item) => (
          <li key={item} className="flex gap-[9px]">
            <span className={cn("flex-none pt-px font-bold", bullet.className)}>{bullet.char}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
