# MyFitnessPalworld — Spécifications projet

Ce dossier contient le corpus de spécifications de **MyFitnessPalworld**, une PWA de suivi alimentaire et nutritionnel, destinée à un usage privé entre l'utilisateur principal et ses proches.

## Structure

- `CLAUDE.md` : instructions de travail obligatoires pour Claude Code.
- `specs/00-overview.md` : vision, périmètre, architecture générale.
- `specs/01-functional-specs.md` : règles fonctionnelles détaillées.
- `specs/02-user-flows.md` : parcours utilisateurs principaux.
- `specs/03-data-model.md` : modèle de données cible.
- `specs/04-api.md` : catalogue d'API DRF.
- `specs/05-permissions-security.md` : permissions, sécurité, confidentialité.
- `specs/06-frontend-ux.md` : React, navigation, responsive, design.
- `specs/07-ai-integrations.md` : Meal Scan, Voice Logging, Meal Planner.
- `specs/08-tests-quality.md` : tests, qualité et définition de fini.
- `specs/09-deployment-railway.md` : déploiement production Railway de zéro.
- `specs/10-coding-rules.md` : conventions de code, Git et migrations.
- `specs/11-external-data-sources.md` : Ciqual, Open Food Facts, USDA fallback.

## Principe de travail

Les règles métier écrites dans ces fichiers font foi. Si une règle n'est pas définie, Claude Code ne doit pas l'inventer silencieusement : il doit soit choisir l'option la plus conservative et la documenter dans le diff, soit demander une décision si elle change le comportement utilisateur ou la sécurité.

Les fonctionnalités sont implémentées progressivement, mais l'architecture doit rester compatible avec l'ensemble de ce corpus.
