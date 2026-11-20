export default function CVCardSkeleton() {
  return (
    <div className="h-full">
      <div className="flex h-full flex-col overflow-hidden rounded-[14px] border border-subtle bg-card p-[9px]">
        <div className="flex-1 min-h-0 animate-pulse rounded-[9px] bg-overlay" />
        <div className="flex-none space-y-2 pt-[11px] px-[5px] pb-[3px]">
          <div className="h-3.5 w-3/4 animate-pulse rounded bg-overlay" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-card-hover" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-card-hover" />
        </div>
      </div>
    </div>
  );
}
