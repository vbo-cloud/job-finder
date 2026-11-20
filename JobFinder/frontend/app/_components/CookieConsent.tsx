"use client";

import Link from "next/link";

import { useConsent } from "@/lib/consent/ConsentContext";

/**
 * Full-width consent bar pinned to the bottom, shown only until the user makes
 * a choice. Deliberately prominent (not a discreet corner card) so the decision
 * is taken up front rather than ignored.
 *
 * CNIL compliance: "Refuser" and "Accepter" are equally prominent (same size,
 * both filled), nothing is captured before an explicit click, and browsing does
 * not count as consent (the bar only closes on a button press). z-40 sits above
 * the legal links (z-30) but below modals (z-50).
 */
export default function CookieConsent() {
  const { consent, hydrated, accept, decline } = useConsent();

  // Wait for the stored choice to load, then show only if none was made yet.
  if (!hydrated || consent !== null) return null;

  return (
    <section
      aria-label="Consentement aux cookies"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-subtle bg-surface px-4 py-4 sm:px-6"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm leading-relaxed text-body">
          {"Bienvenue sur Job Finder. Nous utilisons des cookies et certaines de vos données personnelles à des fins de mesure d'audience, pour améliorer votre expérience. Vos données restent hébergées dans l'UE."}{" "}
          <Link
            href="/confidentialite"
            className="rounded-sm text-accent underline underline-offset-2 transition-colors hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            En savoir plus
          </Link>
        </p>
        <div className="flex flex-none gap-2">
          <button
            type="button"
            onClick={decline}
            className="rounded-xl bg-solid-secondary px-5 py-2.5 text-sm font-semibold text-primary transition-colors hover:bg-solid-secondary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            Refuser
          </button>
          <button
            type="button"
            onClick={accept}
            className="rounded-xl bg-solid-primary px-5 py-2.5 text-sm font-semibold text-on-solid transition-colors hover:bg-solid-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Accepter
          </button>
        </div>
      </div>
    </section>
  );
}
