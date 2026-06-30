# Python Conventions

## Typage et documentation
- Type hints obligatoires sur toutes les fonctions — paramètres et valeur de retour
- Docstrings Google style sur tous les modules, classes et fonctions publiques
- Les fonctions sans docstring sont considérées incomplètes

## Constantes
- Les constantes (noms en MAJUSCULES) sont déclarées immédiatement après les imports, avant tout autre code de niveau module (loggers, variables d'environnement, initialisations de clients)

## Logging
- Utiliser `structlog` exclusivement — jamais `print()` ni `logging` standard
- JSON en production, coloré en dev (contrôlé par `LOG_LEVEL` depuis l'environnement)
- Chaque module configure son logger en tête de fichier : `logger = structlog.get_logger()`
- Les logs d'erreur incluent toujours l'exception : `logger.error("msg", exc_info=True)`

## Variables d'environnement
- Chargées au démarrage du module (niveau module, pas dans les fonctions)
- Une variable manquante lève une `ValueError` explicite avec le nom de la variable
- Ne jamais utiliser de valeur par défaut silencieuse pour une variable critique

## Gestion des erreurs
- Jamais de `except Exception` nu — toujours catcher une exception spécifique
- Dans un bloc `except` dont le seul but est de logger et relancer, utiliser `raise` nu — jamais `raise X(str(e)) from e`. `raise` nu préserve le type exact de l'exception originale. `raise X(str(e)) from e` n'est approprié que si on veut volontairement changer le type de l'exception (cas rare).
- Les ressources (sessions DB, clients Service Bus) sont toujours gérées via context managers (`with`)
- Toute fonction effectuant un appel externe (API, base de données, réseau) doit logger son entrée avec `logger.info` et entourer l'appel d'un `try/except` sur l'exception spécifique de la librairie concernée, avec `logger.error(..., exc_info=True)` et re-raise via `raise ... from e`

## Style
- f-strings exclusivement — pas de `.format()` ni de `%`
- Pas de logique métier dans `main.py` — il orchestre uniquement (appels aux autres modules)
- Une fonction = une responsabilité. Si une fonction fait plus de 40 lignes, la découper.
