"use client";

import { useState } from "react";

import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

export default function HomeClient() {
  const [uploadCount, setUploadCount]           = useState(0);
  const [pendingThumbnail, setPendingThumbnail] = useState<string | null>(null);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection
        onReadyForLibrary={(_name, dataUrl) => {
          setPendingThumbnail(dataUrl ?? null);
          setUploadCount((n) => n + 1);
        }}
      />
      <LibrarySection refreshTrigger={uploadCount} pendingThumbnail={pendingThumbnail} />
    </main>
  );
}
