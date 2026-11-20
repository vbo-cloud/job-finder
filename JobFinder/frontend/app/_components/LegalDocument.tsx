import { ChevronLeft } from "lucide-react";
import Link from "next/link";

/**
 * One block of a legal document. The text lives in plain JS strings (not JSX
 * text nodes) so the legally-worded content is preserved character-for-character
 * without HTML-entity escaping (`react/no-unescaped-entities`) altering it.
 */
export type LegalBlock =
  | { kind: "h2"; text: string }
  | { kind: "p"; text: string }
  | { kind: "ul"; items: string[] }
  /** Tight multi-line block (e.g. a postal address) — one line break between
   * each entry, no paragraph spacing. */
  | { kind: "lines"; lines: string[] };

interface LegalDocumentProps {
  /** Rendered as the page's <h1>. */
  title: string;
  blocks: LegalBlock[];
}

/**
 * Static reading shell shared by the public legal pages (`/mentions-legales`,
 * `/confidentialite`). Server Component on purpose: these pages hold no state
 * and must stay reachable while logged out (no MSAL auth guard), unlike the
 * app's authenticated pages. Reuses the profile/feedback visual surface for
 * consistency.
 */
export default function LegalDocument({ title, blocks }: LegalDocumentProps) {
  return (
    <div className="min-h-screen bg-profile-page">
      {/* Desktop back-to-home bar — mirrors feedback/profile. On mobile the
          global pinned bar (layout.tsx) already covers navigation home. */}
      <div className="fixed inset-x-0 top-0 z-40 hidden h-[52px] items-center bg-profile-surface px-5 md:flex">
        <Link
          href="/"
          className="flex h-8 items-center gap-1 rounded-full border border-soft pl-2 pr-3.5 text-xs font-medium text-strong transition-colors hover:border-default hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={2.5} />
          Accueil
        </Link>
      </div>

      <main className="mx-auto max-w-2xl px-4 pb-16 pt-20 sm:px-10">
        <h1 className="text-xl font-bold leading-tight text-strong">{title}</h1>

        <div className="mt-6 rounded-2xl bg-profile-surface p-4 sm:p-6">
          {blocks.map((block, index) => {
            if (block.kind === "h2") {
              return (
                <h2
                  key={index}
                  className="mt-6 text-base font-semibold text-strong first:mt-0"
                >
                  {block.text}
                </h2>
              );
            }
            if (block.kind === "lines") {
              return (
                <p key={index} className="mt-2 text-sm leading-relaxed text-body">
                  {block.lines.map((line, lineIndex) => (
                    <span key={lineIndex}>
                      {lineIndex > 0 && <br />}
                      {line}
                    </span>
                  ))}
                </p>
              );
            }
            if (block.kind === "ul") {
              return (
                <ul
                  key={index}
                  className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-body"
                >
                  {block.items.map((item, itemIndex) => (
                    <li key={itemIndex}>{item}</li>
                  ))}
                </ul>
              );
            }
            return (
              <p key={index} className="mt-2 text-sm leading-relaxed text-body">
                {block.text}
              </p>
            );
          })}
        </div>
      </main>
    </div>
  );
}
