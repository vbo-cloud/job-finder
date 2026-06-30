"use client";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ reset }: ErrorProps) {
  return (
    <main className="flex h-screen flex-col items-center justify-center gap-4 bg-page">
      <p className="text-sm text-muted">Une erreur est survenue.</p>
      <button
        type="button"
        onClick={reset}
        className="rounded-full border border-default px-4 py-1.5 text-xs text-body transition-colors hover:border-hover hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        Réessayer
      </button>
    </main>
  );
}
