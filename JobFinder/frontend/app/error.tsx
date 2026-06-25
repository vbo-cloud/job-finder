"use client";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ reset }: ErrorProps) {
  return (
    <main className="flex h-screen flex-col items-center justify-center gap-4 bg-[#0a0a0f]">
      <p className="text-sm text-white/40">Une erreur est survenue.</p>
      <button
        type="button"
        onClick={reset}
        className="rounded-full border border-white/20 px-4 py-1.5 text-xs text-white/60 transition-colors hover:border-white/35 hover:text-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
      >
        Réessayer
      </button>
    </main>
  );
}
