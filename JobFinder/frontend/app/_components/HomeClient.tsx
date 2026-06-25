"use client";

import { useCallback, useState } from "react";

import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

export default function HomeClient() {
  // Incremented after each upload to trigger a LibrarySection re-fetch
  const [uploadCount, setUploadCount] = useState(0);

  const handleUploadComplete = useCallback(() => {
    setUploadCount((n) => n + 1);
  }, []);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection onUploadComplete={handleUploadComplete} />
      <LibrarySection refreshTrigger={uploadCount} />
    </main>
  );
}
