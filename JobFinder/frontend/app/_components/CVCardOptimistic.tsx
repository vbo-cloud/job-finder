interface Props {
  thumbnailUrl: string;
}

export default function CVCardOptimistic({ thumbnailUrl }: Props) {
  return (
    <div className="flex w-44 flex-shrink-0 flex-col">
      <div className="flex flex-col gap-2.5 rounded-xl border border-subtle bg-card p-4">
        <div className="relative flex aspect-[3/4] w-full items-center justify-center overflow-hidden rounded-lg bg-overlay">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={thumbnailUrl}
            alt=""
            className="absolute inset-0 h-full w-full object-cover grayscale opacity-50"
          />
          <div className="absolute inset-0 bg-scrim" />
          <svg
            aria-hidden="true"
            className="relative h-5 w-5 animate-spin text-muted"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
        <div className="h-4" />
        <div className="h-3.5" />
        <p className="text-[10px] text-hint">Analyse en cours…</p>
      </div>
      {/* Spacer matching CVCard's always-present delete controls */}
      <div className="h-[42px]" />
    </div>
  );
}
