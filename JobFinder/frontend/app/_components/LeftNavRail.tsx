"use client";

import { FileText, LayoutGrid } from "lucide-react";
import type { ReactNode, SVGProps } from "react";

import { cn } from "@/lib/utils";

export type ActiveSection = "home" | "library" | "cv-detail";

interface LeftNavRailProps {
  activeSection: ActiveSection;
  /** Only meaningful while activeSection === "home": distinguishes the CV
   * layer from the map layer, which share that same snap section. */
  mapActive: boolean;
  mapAvailable: boolean;
  libraryAvailable: boolean;
  offersAvailable: boolean;
  onGoHome: () => void;
  onGoMap: () => void;
  onGoLibrary: () => void;
  onGoOffers: () => void;
}

/** France silhouette ("l'Hexagone") — lucide has no France icon. Path
 * supplied by Vincent (france-contour.svg); recolored to currentColor so it
 * follows the same idle/hover/active states as the other rail icons instead
 * of the original hardcoded white stroke. */
function FranceMapIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 176 176"
      fill="none"
      stroke="currentColor"
      // 14.67 keeps the rendered stroke the same physical thickness as the
      // other icons' strokeWidth="2" on a 24 viewBox, scaled up for this
      // icon's much larger 176 viewBox (2/24 === 14.67/176).
      strokeWidth="14.67"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M141.084,37.649L146.906,42.198L164.301,44.61L158.996,57.457L158.204,70.543L154.962,73.848L149.287,72.461L149.907,77.074L141.256,87.72L141.347,95.976L147.26,92.886L151.95,100.683L151.697,105.864L155.813,112.53L151.598,118.312L155.658,132.264L162.898,134.195L161.834,142.19L150.317,153.123L123.892,149.019L104.573,155.166L103.032,166.164L87.343,168.432L72.338,159.827L67.325,163.606L43.027,154.193L38.135,146.768L45.617,136.234L50.053,100.024L38.239,80.119L29.778,70.251L11.699,61.663L11.751,48.277L27.647,45.673L47.482,51.759L44.956,30.864L55.727,39.349L83.713,26.07L87.519,11.14L97.638,7.568L99.266,13.995L104.643,14.313L110.075,21.633L118.368,30.178L124.401,28.635L134.971,36.668L137.678,38.183Z" />
    </svg>
  );
}

/** Big CV panel on the left, three list rows on the right — mirrors
 * CVDetailSection's own two-column layout (thumbnail + matches list). */
function OffersIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <rect x="3" y="4" width="8" height="16" rx="1.5" />
      <line x1="15" y1="7" x2="21" y2="7" />
      <line x1="15" y1="12" x2="21" y2="12" />
      <line x1="15" y1="17" x2="21" y2="17" />
    </svg>
  );
}

interface NavIconButtonProps {
  label: string;
  active: boolean;
  available: boolean;
  onClick: () => void;
  children: ReactNode;
}

function NavIconButton({ label, active, available, onClick, children }: NavIconButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!available}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-11 w-11 items-center justify-center rounded-full text-muted transition-colors hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
        active && "text-accent hover:text-accent",
        !available && "opacity-40",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Desktop-only pill rail — jumps between the four home-page "pages" (map, CV
 * upload, library, correspondances, in render order) in one click. Hidden
 * below md: the pinned mobile bar (MobileNavMenu) already covers this on
 * phones/tablets.
 * The active icon is driven by scroll position (IntersectionObserver in
 * HomeClient) and, within the shared home/map section, by the map mode —
 * not by which icon was last clicked, so it stays correct on manual scroll.
 */
export default function LeftNavRail({
  activeSection,
  mapActive,
  mapAvailable,
  libraryAvailable,
  offersAvailable,
  onGoHome,
  onGoMap,
  onGoLibrary,
  onGoOffers,
}: LeftNavRailProps) {
  return (
    <nav
      aria-label="Navigation entre les pages"
      // bg-scrim (not bg-surface, used by the other pills in this section)
      // is intentional here: Vincent asked for a dark, near-transparent
      // background rather than a theme-adaptive one.
      className="fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 flex-col items-center gap-5 rounded-full border border-subtle bg-scrim px-1 py-6 shadow-lg md:flex"
    >
      <NavIconButton
        label="Carte — zone de recherche"
        active={activeSection === "home" && mapActive}
        available={mapAvailable}
        onClick={onGoMap}
      >
        <FranceMapIcon className="h-5 w-5" aria-hidden="true" />
      </NavIconButton>
      <NavIconButton
        label="Accueil — import de CV"
        active={activeSection === "home" && !mapActive}
        available
        onClick={onGoHome}
      >
        <FileText className="h-5 w-5" aria-hidden="true" />
      </NavIconButton>
      <NavIconButton
        label="Bibliothèque"
        active={activeSection === "library"}
        available={libraryAvailable}
        onClick={onGoLibrary}
      >
        <LayoutGrid className="h-5 w-5" aria-hidden="true" />
      </NavIconButton>
      <NavIconButton
        label="Offres"
        active={activeSection === "cv-detail"}
        available={offersAvailable}
        onClick={onGoOffers}
      >
        <OffersIcon className="h-5 w-5" aria-hidden="true" />
      </NavIconButton>
    </nav>
  );
}
