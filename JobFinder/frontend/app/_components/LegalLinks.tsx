import Link from "next/link";

import ManageCookiesButton from "@/app/_components/ManageCookiesButton";

/**
 * Discreet legal links pinned to the bottom-left corner on every page. Fixed
 * position (not an in-flow footer) so they stay reachable on the full-height
 * snap-scroll home without disrupting its layout, while remaining visible on
 * the scrollable content pages too. z-30 keeps them below the header (z-50),
 * the nav rail (z-40) and any modal (z-50), so they never float over a dialog.
 *
 * Server Component with one Client island (ManageCookiesButton) for cookie
 * withdrawal — legal notices must stay reachable while logged out (no auth
 * guard).
 */
export default function LegalLinks() {
  const linkClass =
    "text-muted underline-offset-2 transition-colors hover:text-body hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default rounded-sm";

  return (
    <nav
      aria-label="Informations légales"
      className="fixed bottom-2 left-2 z-30 flex items-center gap-2 text-[10.5px] leading-none"
    >
      <Link href="/mentions-legales" className={linkClass}>
        Mentions légales
      </Link>
      <span aria-hidden="true" className="text-hint">
        ·
      </span>
      <Link href="/confidentialite" className={linkClass}>
        Confidentialité
      </Link>
      <span aria-hidden="true" className="text-hint">
        ·
      </span>
      <ManageCookiesButton className={linkClass} />
    </nav>
  );
}
