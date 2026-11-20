---
description: Mettre en place un prompt détaillé et complet afin de faire démarrer une nouvelle tâche délimitée à Claude Code
argument-hint: <description de la demande>
---

Réservé aux sessions locales interactives (Cowork ou Code) : l'étape 4 suppose un
échange humain en aller-retour, ce qu'un run `claude-code-action` en CI ne permet
pas dans une seule invocation (voir `.github/CLAUDE_ACTION.md`). N'utilise pas cette
commande dans ce contexte.

Créer un prompt pour la feature suivante :
$ARGUMENTS

Avant de l'écrire :
1. Vérifie les conventions dans `.claude/skills/` qui seraient pertinentes.
2. Assure-toi de bien connaître le contexte de la demande — vérifie la documentation du projet (`docs/`) si nécessaire.
3. Propose un plan bref.
4. On discute du plan.
5. Une fois le plan validé, crée un fichier dans `docs/prompts/` avec le plan détaillé pour Claude Code. Nomme-le `docs/prompts/prompt-<slug-kebab-case>.md`, dans la continuité des fichiers existants.
