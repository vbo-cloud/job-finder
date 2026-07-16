import { cn } from "@/lib/utils";

interface Props {
  className?: string;
}

// Must match the duration in the `dotPulse` keyframes (globals.css). Kept as a
// constant, and the stagger derived from it as a ratio, so the two can't
// silently drift out of proportion if the keyframe duration ever changes.
const DOT_PULSE_DURATION_S = 1.2;
const DOT_STAGGER_RATIO = 0.15;

/** Three-dot "typing" indicator — purely decorative, color inherited via currentColor. */
export default function AnalyzingDots({ className }: Props) {
  return (
    <span className={cn("inline-flex items-center gap-[3px]", className)} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-[3px] w-[3px] rounded-full bg-current"
          style={{
            animation: `dotPulse ${DOT_PULSE_DURATION_S}s ease-in-out infinite`,
            animationDelay: `${i * DOT_STAGGER_RATIO * DOT_PULSE_DURATION_S}s`,
          }}
        />
      ))}
    </span>
  );
}
