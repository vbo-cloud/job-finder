"use client";

import dynamic from "next/dynamic";

// Leaflet touches window/document at import time — client-only, with a
// pulsing placeholder filling the layer so the map does not pop in while
// Leaflet and the contours load behind the CV upload screen.
const CommuneZonePicker = dynamic(
  () => import("@/app/profile/_components/CommuneZonePicker"),
  {
    ssr: false,
    loading: () => <div className="h-full w-full animate-pulse rounded bg-card" />,
  },
);

interface MapSectionProps {
  communeCodes: string[];
  onChange: (codes: string[]) => void;
  onPaintingChange?: (painting: boolean) => void;
  onAtMinZoomChange?: (atMinZoom: boolean) => void;
  viewResetToken?: number;
}

/**
 * Map layer of the home hero: the commune zone picker in its embedded
 * variant, filling the whole section. HomeMapSection keeps it permanently
 * mounted (blurred/faded behind the CV layer) and reveals it through the
 * camera focus-pull transition.
 */
export default function MapSection({
  communeCodes,
  onChange,
  onPaintingChange,
  onAtMinZoomChange,
  viewResetToken,
}: MapSectionProps) {
  return (
    <div className="absolute inset-0 flex flex-col p-6">
      <div className="min-h-0 flex-1">
        <CommuneZonePicker
          value={communeCodes}
          onChange={onChange}
          variant="embedded"
          onPaintingChange={onPaintingChange}
          onAtMinZoomChange={onAtMinZoomChange}
          viewResetToken={viewResetToken}
        />
      </div>
    </div>
  );
}
