# Frontend / Next.js Conventions

## Server Components vs Client Components
- **Par défaut, tout composant est un Server Component** — Next.js App Router. Ne jamais ajouter `"use client"` par réflexe.
- Ajouter `"use client"` uniquement si le composant utilise : hooks React (`useState`, `useEffect`, `useMsal`…), event handlers (`onClick`, `onChange`…), ou APIs navigateur (`window`, `document`, `localStorage`).
- Les composants MSAL (`useIsAuthenticated`, `useMsal`, `MsalProvider`) sont toujours `"use client"`.
- Pousser `"use client"` aussi bas que possible dans l'arbre : extraire la partie interactive dans un sous-composant plutôt que de marquer toute une page.

## Utilitaire `cn()` — classes Tailwind conditionnelles
- **Toujours utiliser `cn()` pour les classes conditionnelles**, jamais de concaténation de strings ou de template literals.
- `cn()` est défini dans `lib/utils.ts` (`clsx` + `tailwind-merge`) — dépendances : `clsx`, `tailwind-merge`.
- Exemple : `className={cn("rounded px-4 py-2", isActive && "bg-blue-600", className)}`
- Raison : `tailwind-merge` résout les conflits Tailwind silencieux (ex. `bg-blue-500 bg-red-500` → une seule couleur appliquée).

## Dynamic import — librairies lourdes et dépendantes du navigateur
- **Three.js et toute librairie accédant à `window`/`document` doivent être importées dynamiquement avec `ssr: false`.**
- Syntaxe obligatoire :
  ```typescript
  const OrbitAnimation = dynamic(
    () => import("@/components/upload/OrbitAnimation"),
    { ssr: false, loading: () => <div className="h-full w-full" /> }
  );
  ```
- Le composant cible (`OrbitAnimation.tsx`) doit avoir sa propre directive `"use client"`.
- Raison : Three.js appelle `window` à l'import → plante en SSR. Sans `dynamic`, le bundle initial s'alourdit inutilement.

## Three.js — cleanup obligatoire
- Tout composant Three.js **doit** libérer les ressources GPU dans le return de `useEffect`. Une fuite mémoire GPU n'est pas récupérée par le garbage collector JavaScript.
  ```typescript
  useEffect(() => {
    const renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current! });
    const geometry = new THREE.SphereGeometry(1, 32, 32);
    const material = new THREE.MeshStandardMaterial();
    // ... setup scene, animation loop ...
    return () => {
      renderer.dispose();
      geometry.dispose();
      material.dispose();
    };
  }, []);
  ```
- Arrêter la boucle d'animation (`cancelAnimationFrame`) dans le même cleanup.

## Types API — source unique
- Les types des réponses API (ex. `ProfileData`, `CVData`, `MatchData`) sont définis dans **`lib/api/types.ts`**, jamais inline dans les pages.
- Les pages importent les types depuis `@/lib/api/types`.

## `next/image` et `next/font` — jamais de primitives brutes
- **Jamais de balise `<img>` brute** : toujours `next/image` (optimisation WebP, lazy loading, prévention layout shift).
- **Jamais de `<link>` Google Fonts** : toujours `next/font/google` dans `layout.tsx` (intégration au build, zéro flash).
- Exception : SVG inline décoratifs ne nécessitent pas `next/image`.

## Appels API backend
- **Tout appel vers la webapp FastAPI passe exclusivement par `apiClient`** (`lib/api/client.ts`), jamais par `fetch()` direct.
- Raison : `apiClient` injecte automatiquement le Bearer token via l'intercepteur Axios.
- `fetch()` natif est acceptable pour des ressources publiques externes (CDN, APIs tierces sans auth).

## Variables d'environnement publiques (`NEXT_PUBLIC_*`)
- **Toujours référencer une variable `NEXT_PUBLIC_*` en toutes lettres et statiquement** : `process.env.NEXT_PUBLIC_FOO`. Jamais via un accès dynamique (`process.env[name]`, déstructuration calculée, etc.).
- Raison : Next.js n'inline les `NEXT_PUBLIC_*` dans le bundle **client** qu'au prix d'un remplacement textuel à la compilation, qui n'a lieu **que** sur des références statiques. Un accès dynamique laisse la valeur `undefined` côté navigateur (alors qu'elle fonctionne côté serveur) → la page plante au chargement. Si une validation centralisée est souhaitée, lire la valeur statiquement puis la passer à une fonction de validation (ex. `requireEnv("NEXT_PUBLIC_FOO", process.env.NEXT_PUBLIC_FOO)`).
- Les variables sans `NEXT_PUBLIC_` sont uniquement accessibles côté serveur (Server Components, Route Handlers, Server Actions) — elles sont `undefined` dans un Client Component.

## Fichiers de route spéciaux — `loading.tsx` et `error.tsx`
- Toute route qui effectue un fetch de données **doit** avoir un `loading.tsx` (Suspense automatique) et un `error.tsx` (Error Boundary automatique).
- `loading.tsx` : skeleton ou spinner affiché pendant le fetch. Évite de gérer `isLoading` manuellement dans chaque page.
- `error.tsx` : composant `"use client"` avec `{ error, reset }` props. Affiche un message d'erreur et un bouton "Réessayer".

## Groupes de routes — layouts partagés sans impact URL
- Utiliser des route groups `(nom)/` pour partager un layout entre plusieurs pages sans modifier l'URL.
- Exemple : `app/(authenticated)/layout.tsx` — garde d'authentification partagée entre `/library`, `/cv/[id]`, `/profile`.
- Évite de dupliquer la logique de garde dans chaque `page.tsx`.

## Nommage des fichiers
- Composants React : `PascalCase.tsx` (`LoginButton.tsx`, `CVDropzone.tsx`, `OfferCard.tsx`)
- Utilitaires, config, clients : `camelCase.ts` (`msalConfig.ts`, `client.ts`, `utils.ts`)
- Segments de route : `kebab-case/` (`cv/[id]/`, `app/(authenticated)/`)
- Pas de fichier `index.ts` dans les composants (Next.js résout directement le nom de fichier)

## Taille et découpe des composants
- **Un composant = une responsabilité.** Si un composant dépasse ~80 lignes ou mélange deux préoccupations, le découper.
- Colocation : les sous-composants utilisés uniquement par une page vivent dans `app/<route>/_components/` (le `_` exclut le dossier du routing Next.js).
- Les composants réutilisables entre routes vivent dans `components/`.

## `useEffect` — exhaustivité des dépendances
- Ne jamais supprimer une dépendance du tableau pour faire taire ESLint (`react-hooks/exhaustive-deps`).
- Si une fonction cause des re-renders indésirables en dépendance, la stabiliser avec `useCallback`.
- Si une valeur change trop souvent, utiliser une ref (`useRef`) plutôt que de la supprimer des deps.

## `void` pour les promesses ignorées
- Préfixer par `void` les promesses dont on ignore délibérément le résultat dans les event handlers :
  `onClick={() => void handleSave()}`, `onClick={() => void instance.loginRedirect(loginRequest)}`
- Évite le warning TypeScript `no-floating-promises` et documente l'intention explicitement.

## Accessibilité minimale
- Tout bouton sans texte visible a un `aria-label` explicite.
- Toute image `next/image` a un `alt` (chaîne vide `alt=""` si purement décorative).
- Tous les éléments interactifs ont des styles focus visibles : `focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none`.
- HTML sémantique : `<header>`, `<nav>`, `<main>`, `<section>` selon le contexte — pas de `<div>` à la place.
