export default function CVCardSkeleton() {
  return (
    <div className="flex w-44 flex-shrink-0 flex-col">
      <div className="flex flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-4">
        <div className="aspect-[3/4] w-full animate-pulse rounded-lg bg-white/[0.06]" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-white/[0.06]" />
        <div className="h-3.5 w-1/2 animate-pulse rounded bg-white/[0.04]" />
        <div className="h-3.5 w-2/3 animate-pulse rounded bg-white/[0.04]" />
      </div>
      {/* Spacer matching CVCard's always-present delete controls (wire + trash row) */}
      <div className="h-[42px]" />
    </div>
  );
}
