# CLAUDE.md — MyFitnessPalworld

Tu travailles sur **MyFitnessPalworld**, une application web PWA mobile-first de suivi alimentaire et nutritionnel.

## 1. Lecture obligatoire

Avant toute modification importante, lis les spécifications concernées.

Ordre de référence :

1. @specs/00-overview.md
2. @specs/01-functional-specs.md
3. @specs/03-data-model.md
4. @specs/04-api.md
5. @specs/05-permissions-security.md
6. @specs/06-frontend-ux.md
7. @specs/07-ai-integrations.md
8. @specs/08-tests-quality.md
9. @specs/10-coding-rules.md

Pour une tâche de déploiement ou d'infrastructure, lis également @specs/09-deployment-railway.md.
Pour une tâche liée aux aliments externes, lis @specs/11-external-data-sources.md.

## 2. Règles absolues

- Ne jamais inventer silencieusement une règle métier qui contredit les specs.
- Toute donnée utilisateur est **privée par défaut**.
- Toute permission doit être appliquée côté backend, jamais seulement dans React.
- Ne jamais faire confiance au frontend pour l'identité, l'ownership, les calories ou les permissions.
- L'IA n'est jamais une source nutritionnelle de vérité.
- Aucun résultat IA n'est écrit directement dans le journal sans validation utilisateur.
- Les anciennes entrées de journal utilisent des **snapshots immuables** de leurs valeurs nutritionnelles.
- Ne jamais modifier une migration Django déjà appliquée. Créer une nouvelle migration.
- Ne jamais committer de secret, token, clé API, mot de passe ou donnée privée.
- Ne jamais logger un mot de passe, token, photo de progression, image Meal Scan ou audio brut.
- Toujours utiliser le modèle `User` personnalisé du projet.
- Utiliser `Decimal` pour les quantités et valeurs nutritionnelles persistées.
- Les données nutritionnelles inconnues sont `null`, jamais artificiellement `0`.
- Les photos de progression ne sont jamais partageables.

## 3. Workflow de développement

Le projet utilise deux branches principales :

- `develop` : développement local.
- `main` : production.

Il n'est pas obligatoire de créer une branche par feature. Le développeur est seul sur le projet.

Les commits doivent suivre Conventional Commits :

- `feat(scope): description`
- `fix(scope): description`
- `refactor(scope): description`
- `test(scope): description`
- `docs(scope): description`
- `chore(scope): description`
- `perf(scope): description`

Avant un commit significatif :

1. exécuter les tests concernés ;
2. exécuter lint et typecheck ;
3. vérifier les migrations ;
4. vérifier qu'aucun secret n'a été ajouté ;
5. vérifier les permissions ;
6. mettre à jour la documentation si le comportement public change.

## 4. Tâches complexes

Lorsqu'une feature demande plusieurs étapes :

- créer une courte checklist de travail ;
- avancer étape par étape ;
- ne pas considérer la feature terminée tant que les tests ne passent pas ;
- éviter les refactors sans rapport avec la tâche ;
- ne pas supprimer du code fonctionnel simplement pour simplifier l'implémentation.

## 5. Backend

Stack cible :

- Python
- Django
- Django REST Framework
- PostgreSQL
- Celery
- Redis
- Gunicorn en production

Applications Django prévues :

- `accounts`
- `nutrition`
- `diary`
- `recipes`
- `planning`
- `social`
- `progress`
- `ai`
- `notifications`
- `common`

Règles :

- API versionnée sous `/api/v1/`.
- Pagination page/limit, 25 éléments par défaut.
- Validation serveur stricte.
- Services métier séparés des views lorsque la logique n'est pas triviale.
- Les appels externes passent par des clients/services dédiés.
- Les tâches lentes passent par Celery.
- Les permissions queryset + object-level doivent empêcher tout accès horizontal.

## 6. Frontend

Stack cible :

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Tailwind CSS
- shadcn/ui
- React Hook Form
- Zod

Règles :

- mobile-first ;
- mêmes fonctionnalités sur mobile et desktop ;
- bottom navigation sur mobile, sidebar sur desktop ;
- UX quotidienne rapide et utilisable à une main ;
- dark/light/system ;
- pas de logique de sécurité uniquement frontend ;
- invalider/refetch les queries après mutations pertinentes ;
- états loading, empty, error et offline obligatoires.

## 7. IA

Passer exclusivement par une abstraction de service :

- `AIService.analyze_meal()`
- `AIService.parse_voice_log()`
- `AIService.generate_meal_plan()`
- `AIService.generate_recipe()`

Provider initial : `AnthropicProvider`.

Les modèles sont configurables par variables d'environnement et peuvent différer selon les tâches.

Toutes les sorties IA doivent être structurées et validées côté backend avant usage.

## 8. Tests

Toute règle métier importante doit avoir un test.

Backend :

- modèles ;
- services ;
- permissions ;
- API ;
- snapshots ;
- règles de suppression ;
- tâches async.

Frontend :

- composants critiques ;
- formulaires ;
- hooks/logique ;
- états importants.

E2E Playwright :

- demande d'inscription ;
- validation admin ;
- connexion ;
- onboarding ;
- ajout au journal ;
- création recette ;
- planner ;
- partage ;
- permissions critiques.

## 9. Définition de fini

Une tâche n'est terminée que si :

- le comportement correspond aux specs ;
- les permissions sont correctes ;
- les tests concernés passent ;
- lint/typecheck passent ;
- les migrations sont propres ;
- les erreurs sont gérées ;
- les états UI nécessaires existent ;
- la documentation est mise à jour si nécessaire.
