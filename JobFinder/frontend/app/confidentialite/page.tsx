import type { Metadata } from "next";

import LegalDocument, { type LegalBlock } from "@/app/_components/LegalDocument";

export const metadata: Metadata = {
  title: "Politique de confidentialité — job-finder",
  description:
    "Politique de confidentialité de Job Finder : données collectées, finalités, sous-traitants, durée de conservation et droits RGPD.",
};

// Texte à portée légale, validé tel quel avec Vincent — ne pas reformuler
// (cf. docs/prompts/prompt-mentions-legales-confidentialite.md). En
// particulier : une seule ligne « Microsoft Azure » dans les sous-traitants,
// pas d'entrée « OpenAI » distincte — Job Finder utilise le service Azure
// OpenAI hébergé par Microsoft (jamais OpenAI Inc.). Résidence des données
// depuis la PR #263 (SKU Azure OpenAI passé en DataZoneStandard) : stockage au
// repos en France Centre, mais traitement IA dans la zone de données « Union
// européenne » de Microsoft (UE + EEE + Suisse, pays adéquat) — d'où la
// formulation « Transferts hors Union européenne » ci-dessous, et non plus
// l'ancienne affirmation « aucun transfert / tout hébergé en France ».
const blocks: LegalBlock[] = [
  { kind: "h2", text: "Responsable du traitement" },
  { kind: "p", text: "Vincent Boutin — legal@vincentboutin.dev" },
  { kind: "h2", text: "Données collectées" },
  {
    kind: "ul",
    items: [
      "Données de compte : identifiant de connexion (fournisseur d'authentification), nom affiché",
      "CV : contenu textuel du CV, compétences et codes ROME extraits par analyse automatisée",
      "Préférences d'emploi : localisation recherchée, type de contrat, niveau d'expérience",
      "Données d'usage du produit : pages consultées, actions réalisées dans l'application, à des fins de mesure d'audience et d'amélioration du produit",
    ],
  },
  { kind: "h2", text: "Finalités" },
  {
    kind: "ul",
    items: [
      "Fournir le service : analyse du CV, mise en correspondance avec des offres d'emploi, recommandations",
      "Mesurer l'usage du produit pour l'améliorer",
    ],
  },
  { kind: "h2", text: "Base légale" },
  {
    kind: "p",
    text: "Exécution du contrat (fourniture du service demandé) et, pour l'analyse IA du CV, consentement de l'utilisateur (upload volontaire du document).",
  },
  { kind: "h2", text: "Sous-traitants et destinataires" },
  {
    kind: "ul",
    items: [
      "Microsoft Azure (service Azure OpenAI, base de données PostgreSQL, stockage de fichiers) — région France Centre, Union européenne. Politique de confidentialité de Microsoft : privacy.microsoft.com/privacystatement. Engagements de protection des données : Microsoft Products and Services Data Protection Addendum (microsoft.com/licensing/docs, rechercher \"DPA\").",
      "PostHog (mesure d'audience) — hébergement Union européenne (PostHog Cloud EU)",
    ],
  },
  { kind: "p", text: "Aucune donnée n'est vendue ni partagée à des fins publicitaires." },
  { kind: "h2", text: "Cookies" },
  { kind: "p", text: "Deux types de cookies peuvent être utilisés :" },
  {
    kind: "ul",
    items: [
      "Cookies strictement nécessaires : indispensables à la connexion et au fonctionnement du service (authentification). Ils ne requièrent pas de consentement.",
      "Cookies de mesure d'audience (PostHog, hébergé dans l'Union européenne) : déposés uniquement si vous les acceptez, pour comprendre l'usage du produit et l'améliorer.",
    ],
  },
  {
    kind: "p",
    text: "Vous pouvez accepter ou refuser les cookies de mesure d'audience à tout moment via le lien « Gérer les cookies » en bas de page. Un refus n'affecte en rien l'utilisation de l'application.",
  },
  { kind: "h2", text: "Transferts hors Union européenne" },
  {
    kind: "p",
    text: "Les données sont hébergées et traitées dans la zone de données « Union européenne » de Microsoft Azure : l'Union européenne et l'Espace économique européen (Islande, Liechtenstein, Norvège), ainsi que la Suisse, qui bénéficie d'une décision d'adéquation de la Commission européenne. Aucun transfert vers un pays tiers hors de cette zone.",
  },
  {
    kind: "p",
    text: "À des fins de détection d'abus, Microsoft peut conserver temporairement les requêtes envoyées à l'IA (jusqu'à 30 jours) au sein de cette même zone.",
  },
  { kind: "h2", text: "Durée de conservation" },
  {
    kind: "p",
    text: "Les données sont conservées tant que le compte utilisateur est actif. Elles sont supprimables à tout moment par l'utilisateur, notamment en cas de suppression de compte.",
  },
  { kind: "h2", text: "Droits des utilisateurs" },
  {
    kind: "p",
    text: "Conformément au RGPD, chaque utilisateur dispose d'un droit d'accès, de rectification, d'effacement, d'opposition et de portabilité de ses données. Le compte et l'ensemble des données associées peuvent être supprimés à tout moment depuis la page profil. Pour toute autre demande : legal@vincentboutin.dev.",
  },
  {
    kind: "p",
    text: "Chaque utilisateur peut également introduire une réclamation auprès de la CNIL (www.cnil.fr).",
  },
];

export default function ConfidentialitePage() {
  return <LegalDocument title="Politique de confidentialité" blocks={blocks} />;
}
