"use client";

import { useCallback, useState } from "react";
import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

export default function HomeClient() {
  const [uploadCount, setUploadCount]         = useState(0);
  const [libraryAccessible, setLibraryAccessible] = useState(false);

  const handleUploadComplete = useCallback(() => {
    setUploadCount((n) => n + 1);
  }, []);

  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection onUploadComplete={handleUploadComplete} libraryAccessible={libraryAccessible} />
      <LibrarySection refreshTrigger={uploadCount} onAccessibilityChange={setLibraryAccessible} />
    </main>
  );
}
