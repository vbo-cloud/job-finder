import { Lock } from "lucide-react";

export default function CVCardLocked() {
  return (
    <div
      title="Emplacement non disponible pour le moment"
      className="flex h-full items-center justify-center rounded-[14px] border-[1.5px] border-dashed border-faint bg-card"
    >
      <Lock aria-hidden="true" width={16} height={16} strokeWidth={1.5} className="text-muted" />
    </div>
  );
}
