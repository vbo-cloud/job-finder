"use client";

import { useState } from "react";

import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

export default function HomeClient() {
  // Incremented after each upload to trigger a LibrarySection re-fetch
  const [uploadCount, setUploadCount] = useState(0);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection
        onReadyForLibrary={() => setUploadCount((n) => n + 1)}
      />
      <LibrarySection refreshTrigger={uploadCount} />
    </main>
  );
}
