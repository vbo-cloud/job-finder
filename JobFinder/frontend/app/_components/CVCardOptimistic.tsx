interface Props {
  thumbnailUrl: string;
}

export default function CVCardOptimistic({ thumbnailUrl }: Props) {
  return (
    <div className="relative h-full">
      <div className="flex h-full flex-col overflow-hidden rounded-[14px] border border-subtle bg-card p-[9px]">
        <div className="relative flex flex-1 min-h-0 items-center justify-center overflow-hidden rounded-[9px] border border-faint bg-card">
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
        <div className="flex-none pt-[11px] px-[5px] pb-[3px]">
          <p className="text-[12px] text-hint">Analyse en cours…</p>
        </div>
      </div>
    </div>
  );
}
