/** Animated placeholder card displayed while CVs are loading. */
export default function CVCardSkeleton() {
  return (
    <div className="flex w-36 flex-shrink-0 flex-col gap-2.5 rounded-xl border border-subtle bg-card p-4">
      <div className="aspect-[3/4] w-full animate-pulse rounded-lg bg-overlay" />
      <div className="h-2 w-3/4 animate-pulse rounded bg-overlay" />
      <div className="h-2 w-1/2 animate-pulse rounded bg-card-hover" />
    </div>
  );
}
