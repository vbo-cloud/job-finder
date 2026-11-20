"use client";

import { cn } from "@/lib/utils";

interface Props {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Position-dependent spacing (e.g. mb-4 above the list, mt-5 below) */
  className?: string;
}

/** Visible page numbers: first/last always shown, a window around the current
 * page, `null` marking a collapsed gap (rendered as an ellipsis). */
function visiblePages(page: number, totalPages: number): (number | null)[] {
  const pages = new Set<number>([1, totalPages]);
  for (let p = page - 1; p <= page + 1; p++) {
    if (p >= 1 && p <= totalPages) pages.add(p);
  }
  const sorted = Array.from(pages).sort((a, b) => a - b);
  const items: (number | null)[] = [];
  let prev = 0;
  for (const p of sorted) {
    if (p - prev === 2) items.push(prev + 1);
    else if (p - prev > 2) items.push(null);
    items.push(p);
    prev = p;
  }
  return items;
}

const navButtonClass =
  "border border-soft rounded-[9px] px-[11px] py-1.5 text-[12.5px] text-body bg-page cursor-pointer transition-colors hover:border-default disabled:opacity-40 disabled:cursor-default disabled:hover:border-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default";

export default function PaginationBar({ page, totalPages, onPageChange, className }: Props) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="Pagination des offres" className={cn("flex items-center justify-center flex-wrap gap-1.5", className)}>
      <button onClick={() => onPageChange(page - 1)} disabled={page === 1} className={navButtonClass}>
        Précédent
      </button>
      {visiblePages(page, totalPages).map((p, i) =>
        p === null ? (
          <span key={`gap-${i}`} className="px-1 text-[12.5px] text-muted">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            aria-current={p === page ? "page" : undefined}
            aria-label={`Page ${p}`}
            className={cn(
              "min-w-[32px] border rounded-[9px] px-2 py-1.5 text-[12.5px] cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
              p === page
                ? "border-default bg-overlay text-strong font-semibold"
                : "border-soft bg-page text-body hover:border-default",
            )}
          >
            {p}
          </button>
        ),
      )}
      <button onClick={() => onPageChange(page + 1)} disabled={page === totalPages} className={navButtonClass}>
        Suivant
      </button>
    </nav>
  );
}
