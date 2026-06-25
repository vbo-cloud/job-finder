"use client";

import { useState } from "react";
import UploadSection from "./UploadSection";

interface PendingCv {
  name: string;
  thumbnail: string | null;
}

export default function HomeClient() {
  const [pendingCv, setPendingCv] = useState<PendingCv | null>(null);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection
        onReadyForLibrary={(name, thumbnail) => setPendingCv({ name, thumbnail })}
      />

      <section id="library" className="h-dvh snap-start bg-[#0a0a0f] px-6 py-8">
        <p className="mb-5 text-[9px] tracking-widest text-white/20">BIBLIOTHÈQUE</p>

        {pendingCv ? (
          <div className="inline-flex w-40 flex-col gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] p-4">
            {/* Thumbnail + spinner overlay */}
            <div className="relative aspect-[3/4] w-full overflow-hidden rounded">
              {pendingCv.thumbnail ? (
                // data: URL — next/image brings no benefit here (local blob, already optimised)
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={pendingCv.thumbnail}
                  alt="Miniature du CV"
                  className="h-full w-full object-cover grayscale"
                />
              ) : (
                <div className="h-full w-full bg-white/[0.06]" />
              )}
              {/* Dark overlay + spinner over the thumbnail */}
              <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                <svg className="h-5 w-5 animate-spin text-white/60" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z" />
                </svg>
              </div>
            </div>
            <p className="truncate text-[11px] text-white/50">{pendingCv.name}</p>
            <p className="text-[10px] text-white/25">Analyse en cours…</p>
          </div>
        ) : (
          <p className="mt-20 text-center text-xs text-white/15">Aucun CV importé</p>
        )}
      </section>
    </main>
  );
}
