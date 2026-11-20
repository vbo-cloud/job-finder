---
name: conventions-python
description: Conventions Python obligatoires du projet Job Finder — type hints partout, docstrings Google style, logging structlog exclusif (JSON en prod, exploitable par Application Insights), variables d'environnement fail-fast au démarrage du module, gestion d'erreurs (except spécifique, raise nu vs raise ... from e), f-strings, taille des fonctions. Utilise ce skill avant d'écrire ou modifier tout fichier .py — agents Container App Jobs, workers Service Bus, scripts, modules backend FastAPI — dès qu'une fonction, un logger, une variable d'environnement, ou un appel externe (API/DB/réseau) apparaît, même si l'utilisateur ne mentionne pas "convention" ou "style".
---

# Python Conventions

## Typage et documentation
- Type hints obligatoires sur toutes les fonctions — paramètres et valeur de retour. Raison : le projet n'a pas de suite de tests exhaustive ; les type hints sont la première ligne de défense contre les erreurs d'appel entre modules (agents, pipelines, API).
- Docstrings Google style sur tous les modules, classes et fonctions publiques. Raison : ce code est appelé à être repris par Claude Code lui-même — une docstring claire réduit le risque de mésinterprétation du contrat d'une fonction.
- Les fonctions sans docstring sont considérées incomplètes

## Constantes
- Les constantes (noms en MAJUSCULES) sont déclarées immédiatement après les imports, avant tout autre code de niveau module (loggers, variables d'environnement, initialisations de clients)

## Logging
- Utiliser `structlog` exclusivement — jamais `print()` ni `logging` standard. Raison : le format JSON structuré est nécessaire pour exploiter les logs dans Azure Monitor / Application Insights ; `print()` et `logging` standard ne produisent pas ce format.
- JSON en production, coloré en dev (contrôlé par `LOG_LEVEL` depuis l'environnement)
- Chaque module configure son logger en tête de fichier : `logger = structlog.get_logger()`
- Les logs d'erreur incluent toujours l'exception : `logger.error("msg", exc_info=True)`

## Variables d'environnement
- Chargées au démarrage du module (niveau module, pas dans les fonctions)
- Une variable manquante lève une `ValueError` explicite avec le nom de la variable. Raison : un agent qui découvre une variable manquante en cours d'exécution peut laisser une ressource externe (Service Bus, DB) dans un état incohérent — fail-fast au démarrage évite ce scénario.
- Ne jamais utiliser de valeur par défaut silencieuse pour une variable critique

## Gestion des erreurs
- Jamais de `except Exception` nu — toujours catcher une exception spécifique
- Dans un bloc `except` dont le seul but est de logger et relancer, utiliser `raise` nu — jamais `raise X(str(e)) from e`. `raise` nu préserve le type exact de l'exception originale. `raise X(str(e)) from e` n'est approprié que si on veut volontairement changer le type de l'exception (cas rare).
- Les ressources (sessions DB, clients Service Bus) sont toujours gérées via context managers (`with`)
- Toute fonction effectuant un appel externe (API, base de données, réseau) doit logger son entrée avec `logger.info` et entourer l'appel d'un `try/except` sur l'exception spécifique de la librairie concernée, avec `logger.error(..., exc_info=True)` et re-raise via `raise ... from e`

## Style
- f-strings exclusivement — pas de `.format()` ni de `%`
- Pas de logique métier dans `main.py` — il orchestre uniquement (appels aux autres modules). Raison : garde la logique métier testable et réutilisable indépendamment du point d'entrée.
- Une fonction = une responsabilité. Si une fonction fait plus de 40 lignes, la découper. Raison : une fonction longue est plus difficile à relire — pour un humain comme pour Claude Code qui n'a qu'une fenêtre de contexte limitée sur le fichier.
