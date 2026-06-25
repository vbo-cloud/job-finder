"use client";

import LibrarySection from "./LibrarySection";
import UploadSection from "./UploadSection";

export default function HomeClient() {
  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-scroll">
      <UploadSection />
      <LibrarySection />
    </main>
  );
}
