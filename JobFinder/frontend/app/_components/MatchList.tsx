import type { MatchOut, RomeCodeEntry } from "@/lib/api/types";
import MatchItem from "./MatchItem";

interface Props {
  matches: MatchOut[];
  loading: boolean;
  romeCodesDict: Record<string, RomeCodeEntry>;
}

export const SKELETON_COUNT = 5;

export default function MatchList({ matches, loading, romeCodesDict }: Props) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: SKELETON_COUNT }, (_, i) => (
          <div key={i} className="h-16 rounded-xl bg-card animate-pulse" />
        ))}
      </div>
    );
  }

  if (matches.length === 0) {
    return <p className="text-xs text-label mt-8 text-center">Aucun match trouvé</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {matches.map((match, i) => (
        <MatchItem key={match.offer.id ?? i} match={match} romeCodesDict={romeCodesDict} />
      ))}
    </div>
  );
}
