# ADR-010 : Stratégie de collecte des offres d'emploi

**Statut :** Accepté
**Date :** 2026-05-01
**Décideur :** Vincent Boutin

---

## Contexte

L'agent de collecte de job-finder a besoin d'un flux d'offres d'emploi frais et structuré. Trois approches : les APIs officielles des job boards, le scraping web, ou les flux RSS/agrégateurs. La qualité, la légalité et la pérennité de la source déterminent directement la valeur du produit.

---

## Décision

**API France Travail (ex-Pôle Emploi)** comme source primaire, complétée par d'autres APIs publiques françaises selon les besoins.

---

## Options considérées

### Option A : APIs officielles

| Dimension | Évaluation |
|---|---|
| Légalité | ✅ Totale — usage autorisé explicitement |
| Coût | Gratuit (France Travail API, Hello Work, Apec) |
| Qualité des données | Très bonne — données structurées, normalisées |
| Volume | France Travail : ~500K offres actives en permanence |
| Stabilité | Excellente — API versionnée, SLA garanti |

**France Travail API (offres-emploi v2)** : API REST publique, gratuite, ~500K offres en temps réel, données très structurées (titre, compétences, contrat, localisation, salaire). Inscription sur francetravail.io requise, accès immédiat.

**Autres APIs à considérer :** Apec (cadres), Hello Work, RegionsJob — toutes ont des APIs documentées et accessibles.

**Contre :** LinkedIn API et Indeed sont quasi-inaccessibles (réservés aux partenaires officiels avec contrat commercial).

---

### Option B : Scraping web

| Dimension | Évaluation |
|---|---|
| Légalité | ⚠️ Risquée — violation des CGU de la plupart des job boards |
| Coût | Faible en code, élevé en maintenance |
| Qualité des données | Variable — parsing HTML fragile |
| Volume | Potentiellement élevé mais instable |
| Stabilité | Mauvaise — les sites changent leur structure régulièrement |

**Pour :** accès à des sources sans API.

**Contre :** CGU interdisant le scraping sur LinkedIn, Indeed, etc. Risque juridique réel. Maintenance continue à chaque refonte de site. IP blocking. Pour un projet portfolio public, c'est un risque inutile.

---

### Option C : Flux RSS / agrégateurs

| Dimension | Évaluation |
|---|---|
| Légalité | ✅ — RSS est conçu pour être consommé |
| Coût | Gratuit |
| Qualité | Faible — peu structuré, données minimales |
| Volume | Limité |

**Pour :** simple à implémenter.

**Contre :** données trop peu structurées pour un matching de qualité. Insuffisant comme source principale.

---

## Analyse des compromis

France Travail API résout tous les problèmes d'un coup : légalité totale, données riches et structurées, volume massif, gratuité. C'est la source évidente pour un projet centré sur le marché de l'emploi français. Le scraping apporterait du volume mais au prix d'un risque juridique et d'une maintenance continue incompatible avec un projet solo.

**Architecture de collecte :**
```
Agent Collecte → France Travail API (offres fraîches quotidiennement)
              → Normalisation des données
              → Azure Blob Storage (offres brutes JSON)
              → Queue Service Bus "offers-collected"
              → Agent Analyse
```

---

## Conséquences

- ✅ Zéro risque juridique
- ✅ ~500K offres disponibles immédiatement, données très structurées
- ✅ Gratuit — pas de coût de collecte
- ✅ Données conformes RGPD (source officielle française)
- ⚠️ Couverture limitée au marché français — extension internationale = nouveau problème à traiter
- ⚠️ Inscription sur francetravail.io requise avant d'accéder à l'API

---

## Actions suivantes

- [ ] S'inscrire sur francetravail.io et créer une application pour obtenir `client_id` / `client_secret`
- [ ] Stocker les credentials dans Key Vault
- [ ] Implémenter l'agent collecte avec OAuth2 + pagination de l'API
- [ ] Définir la fréquence de collecte (quotidienne recommandée)
