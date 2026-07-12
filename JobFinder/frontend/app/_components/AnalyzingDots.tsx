import { cn } from "@/lib/utils";

interface Props {
  className?: string;
}

/** Three-dot "typing" indicator — purely decorative, color inherited via currentColor. */
export default function AnalyzingDots({ className }: Props) {
  return (
    <span className={cn("inline-flex items-center gap-[3px]", className)} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-[3px] w-[3px] rounded-full bg-current [animation:dotPulse_1.2s_ease-in-out_infinite]"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </span>
  );
}
