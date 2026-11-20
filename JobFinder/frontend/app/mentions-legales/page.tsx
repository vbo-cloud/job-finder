import type { Metadata } from "next";

import LegalDocument, { type LegalBlock } from "@/app/_components/LegalDocument";

export const metadata: Metadata = {
  title: "Mentions légales — job-finder",
  description:
    "Mentions légales de Job Finder : éditeur, hébergeur et directeur de la publication.",
};

// Texte à portée légale, validé tel quel avec Vincent — ne pas reformuler
// (cf. docs/prompts/prompt-mentions-legales-confidentialite.md).
const blocks: LegalBlock[] = [
  { kind: "h2", text: "Éditeur" },
  {
    kind: "p",
    text: "Le site et l'application Job Finder (projet « vbo-cloud ») sont édités par Vincent Boutin, personne physique agissant à titre non professionnel (projet personnel / portfolio, hors activité commerciale).",
  },
  { kind: "p", text: "Contact : legal@vincentboutin.dev" },
  {
    kind: "p",
    text: "Conformément à l'article 6-III de la loi n° 2004-575 du 21 juin 2004 pour la confiance dans l'économie numérique, l'éditeur, personne physique agissant à titre non professionnel, n'est pas tenu de rendre publique son adresse personnelle ; celle-ci est tenue à disposition de l'hébergeur.",
  },
  { kind: "h2", text: "Hébergement" },
  {
    kind: "p",
    text: "Le service est hébergé par Microsoft, sur l'infrastructure Microsoft Azure (région France Centre pour l'hébergement de l'application et le stockage des données).",
  },
  {
    kind: "lines",
    lines: [
      "Microsoft France",
      "SIREN 327 733 184",
      "37 quai du Président Roosevelt, 92130 Issy-les-Moulineaux, France",
    ],
  },
  { kind: "h2", text: "Directeur de la publication" },
  { kind: "p", text: "Vincent Boutin" },
];

export default function MentionsLegalesPage() {
  return <LegalDocument title="Mentions légales" blocks={blocks} />;
}
