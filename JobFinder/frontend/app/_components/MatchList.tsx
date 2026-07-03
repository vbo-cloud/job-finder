import MatchItem, { type MatchItemData } from "./MatchItem";

export type { MatchItemData };

export const SKELETON_COUNT = 5;

interface Props {
  items: MatchItemData[];
  loading: boolean;
  rejectedCount: number;
  onRestoreAll: () => void;
}

export default function MatchList({ items, loading, rejectedCount, onRestoreAll }: Props) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: SKELETON_COUNT }, (_, i) => (
          <div key={i} className="h-16 rounded-xl bg-card animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[10px]">
      {rejectedCount > 0 && (
        <div className="flex items-center justify-between gap-3 px-3.5 py-2.5 bg-overlay border border-subtle rounded-[10px]">
          <span className="text-[12.5px] text-muted">
            {rejectedCount} offre{rejectedCount > 1 ? "s" : ""} masquée{rejectedCount > 1 ? "s" : ""}
          </span>
          <button
            onClick={onRestoreAll}
            className="text-[12.5px] font-semibold text-body underline hover:text-strong transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-default rounded"
          >
            Réafficher
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <p className="text-xs text-label mt-8 text-center">Aucune offre ne correspond</p>
      ) : (
        items.map((item) => (
          <MatchItem key={item.match.offer.id} {...item} />
        ))
      )}
    </div>
  );
}
