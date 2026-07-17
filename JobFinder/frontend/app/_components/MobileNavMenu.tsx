"use client";

import { Briefcase, Home, Library, Menu, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/** Home snap sections reachable from the menu, in page order. */
const SECTION_ENTRIES = [
  { id: "home", label: "Accueil", Icon: Home },
  { id: "library", label: "Bibliothèque", Icon: Library },
  { id: "cv-detail", label: "Correspondances", Icon: Briefcase },
] as const;

function sectionVisible(id: string): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  // checkVisibility covers sections that are mounted but display:none (the
  // empty library carries a `hidden` class). jsdom doesn't implement it —
  // fall back to "visible", tests control availability by adding/removing
  // the element instead.
  return (el as { checkVisibility?: () => boolean }).checkVisibility?.() ?? true;
}

/**
 * Mobile navigation menu — the top-left burger of the pinned mobile bar
 * (layout.tsx). On phones the home page no longer navigates by swipe between
 * its full-screen sections: this menu is the way to move around. Section
 * entries scroll the home snap container programmatically (or land on the
 * home page first when opened from another route); "Mon profil" is a plain
 * route link. Entry availability is sampled when the menu opens — the
 * library and the correspondances sections only exist once a CV is uploaded
 * or selected.
 */
export default function MobileNavMenu() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [visibleSections, setVisibleSections] = useState<ReadonlySet<string>>(new Set());
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on any press outside the menu — same pattern as AuthButton.
  useEffect(() => {
    if (!open) return;
    function handleOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const toggle = () => {
    setOpen((wasOpen) => {
      if (!wasOpen) {
        // Sampled at open time: sections mount/unmount as CVs are uploaded
        // and selected — a live subscription would be overkill for a panel
        // that only matters while it's on screen.
        setVisibleSections(
          new Set(SECTION_ENTRIES.filter((s) => sectionVisible(s.id)).map((s) => s.id)),
        );
      }
      return !wasOpen;
    });
  };

  const goToSection = (id: string) => {
    setOpen(false);
    if (pathname !== "/") {
      // The sections only exist on the home page — land there instead.
      router.push("/");
      return;
    }
    // Instant jump on purpose: a smooth scroll stalls midway on the
    // overflow-hidden mobile snap container (Chrome drops the animation when
    // nested scrollers are involved), and menu navigation should feel like
    // switching pages anyway.
    document.getElementById(id)?.scrollIntoView();
  };

  const onHome = pathname === "/";

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls="mobile-nav-panel"
        aria-label={open ? "Fermer le menu de navigation" : "Ouvrir le menu de navigation"}
        className="flex h-11 w-11 items-center justify-center rounded-full text-body transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        {open ? (
          <X className="h-5 w-5" aria-hidden="true" />
        ) : (
          <Menu className="h-5 w-5" aria-hidden="true" />
        )}
      </button>

      {open && (
        <nav
          id="mobile-nav-panel"
          aria-label="Navigation principale"
          className="absolute left-0 top-full z-50 mt-1 w-60 rounded-xl border border-soft bg-surface p-1.5 shadow-2xl"
        >
          {SECTION_ENTRIES.map(({ id, label, Icon }) => {
            // Away from the home page every section entry stays active: it
            // navigates to the home page, where the section can be reached.
            const enabled = !onHome || visibleSections.has(id);
            return (
              <button
                key={id}
                type="button"
                disabled={!enabled}
                onClick={() => goToSection(id)}
                className={cn(
                  "flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-sm text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default",
                  enabled ? "hover:bg-overlay" : "opacity-40",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </button>
            );
          })}
          <div className="mx-2 my-1 h-px bg-card-hover" />
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm text-primary transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            <UserRound className="h-4 w-4" aria-hidden="true" />
            Mon profil
          </Link>
        </nav>
      )}
    </div>
  );
}
