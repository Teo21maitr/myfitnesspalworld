# MyFitnessPalworld

PWA mobile-first de suivi alimentaire et nutritionnel, à usage privé.

Ce dépôt est un monorepo : un backend Django/DRF, un frontend React/Vite, et le corpus de
spécifications qui fait foi pour toutes les règles métier.

> **État actuel : comptes, objectifs et référentiel d'aliments.** Un utilisateur peut demander un
> compte, être accepté, se connecter, dérouler l'onboarding, obtenir un objectif calorique calculé,
> puis rechercher parmi les 3 185 aliments de la table Ciqual et créer ses propres aliments. Le
> journal, les recettes, le planner, la progression, le social et l'IA restent à faire.

## Sommaire

- [Prérequis](#prérequis)
- [Installation](#installation)
- [Lancement avec Docker](#lancement-avec-docker)
- [Lancement hors Docker](#lancement-hors-docker)
- [Migrations](#migrations)
- [Superutilisateur](#superutilisateur)
- [Authentification](#authentification)
- [Objectifs nutritionnels](#objectifs-nutritionnels)
- [Aliments](#aliments)
- [Tests, lint et typecheck](#tests-lint-et-typecheck)
- [Variables d'environnement](#variables-denvironnement)
- [Structure du dépôt](#structure-du-dépôt)
- [Conventions](#conventions)
- [Spécifications](#spécifications)

## Prérequis

| Outil | Version | Nécessaire pour |
| --- | --- | --- |
| Docker + Docker Compose | Docker 28+ | environnement complet |
| Python | 3.13 | backend hors Docker |
| Node.js | 22 LTS | frontend hors Docker |

Le backend cible **Python 3.13** et **Django 5.2 LTS**. Avec pyenv :

```bash
pyenv install 3.13.9
```

## Installation

```bash
git clone <url-du-depot> myfitnesspalworld
cd myfitnesspalworld
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Générer une clé secrète Django et la reporter dans `DJANGO_SECRET_KEY` :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

`.env` est ignoré par git et ne doit jamais être commité.

## Lancement avec Docker

```bash
docker compose up
```

Sept services démarrent : `db` (PostgreSQL 17), `redis` (Redis 8), `backend` (Django),
`worker` et `beat` (Celery), `frontend` (Vite) et `mailpit` (capture des emails). Les
migrations sont appliquées automatiquement au démarrage du backend.

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| API | http://localhost:8001/api/v1/ |
| Health check | http://localhost:8001/health/ |
| Admin Django | http://localhost:8001/admin/ |
| Mailpit (emails de dev) | http://localhost:8025 |

> **Ports décalés.** Les ports par défaut sont 8001 (API), 5433 (PostgreSQL) et 6380 (Redis)
> pour cohabiter avec d'autres projets qui occupent souvent 8000 et 5432. Ils sont
> configurables par `BACKEND_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `FRONTEND_PORT`,
> `MAILPIT_UI_PORT` et `MAILPIT_SMTP_PORT`.

Commandes utiles :

```bash
docker compose logs -f backend
docker compose exec backend python manage.py migrate
docker compose down          # arrêter
docker compose down -v       # arrêter et supprimer les volumes de données
```

## Lancement hors Docker

Les bases de données restent le plus simple à lancer via Docker :

```bash
docker compose up -d db redis
```

### Backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Migrations

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations --check --dry-run   # vérifié par la CI
```

Migrations existantes :

| Migration | Contenu |
| --- | --- |
| `accounts/0001_initial` | modèle `User` personnalisé |
| `common/0001_enable_postgres_extensions` | extensions `pg_trgm` et `unaccent` |
| `accounts/0002_registrationrequest_user_token_version_userprofile_and_more` | `RegistrationRequest`, `UserProfile`, `UserSettings`, `User.token_version` |
| `notifications/0001_initial` | `EmailLog` |
| `accounts/0003_update_username_validator_message` | message de validation du username |
| `nutrition/0001_initial` | `NutritionGoal`, `NutritionGoalDayOverride` |
| `nutrition/0002_food_…` | `Food`, `FoodNutrition`, `FoodPortion`, favoris, historique |
| `nutrition/0003_fix_food_portion_unique_nulls` | unicité des portions officielles |
| `progress/0001_initial` | `WeightEntry` |

> Une migration déjà appliquée n'est **jamais** modifiée : il faut en créer une nouvelle.

## Superutilisateur

```bash
# Docker
docker compose exec backend python manage.py createsuperuser

# hors Docker
cd backend && python manage.py createsuperuser
```

La commande ne demande que le nom d'utilisateur et le mot de passe : l'email est facultatif
dans ce projet et peut être renseigné ensuite depuis l'admin.

## Authentification

### Endpoints

```text
POST   /api/v1/auth/register-request/    demande de compte
POST   /api/v1/auth/login/               connexion (pose les cookies)
POST   /api/v1/auth/refresh/             rotation de la session
POST   /api/v1/auth/logout/              déconnexion de l'appareil courant
POST   /api/v1/auth/logout-all/          révocation de toutes les sessions
GET    /api/v1/auth/me/                  compte courant
GET    /api/v1/auth/csrf/                amorçage du cookie CSRF
POST   /api/v1/auth/forgot-password/     envoi du lien de réinitialisation
POST   /api/v1/auth/reset-password/      application d'un nouveau mot de passe

GET    /api/v1/profile/                  identité
PATCH  /api/v1/profile/
GET    /api/v1/profile/settings/         thème, format de date
PATCH  /api/v1/profile/settings/

POST   /api/v1/account/change-password/
DELETE /api/v1/account/                  suppression définitive
```

### Cookies

| Cookie | Contenu | HttpOnly | Chemin | Durée |
| --- | --- | --- | --- | --- |
| `mfp_access` | access JWT | oui | `/` | 15 min |
| `mfp_refresh` | refresh JWT | oui | `/api/v1/auth/` | 30 jours |
| `mfp_csrftoken` | jeton CSRF | non (lu par le JS) | `/` | session |

Aucun token n'est stocké dans `localStorage`. `Secure` et `SameSite` sont pilotés par
`AUTH_COOKIE_SECURE` et `AUTH_COOKIE_SAMESITE` : `Lax` sans `Secure` en local, `None` avec
`Secure` en production où le frontend et l'API sont sur des sous-domaines distincts.

### CSRF

Une authentification portée par un cookie est envoyée automatiquement par le navigateur : elle
est donc exposée au CSRF, que DRF n'applique pas à ses vues par défaut. `CookieJWTAuthentication`
rétablit la vérification de Django dès que le token provient du cookie. Le frontend récupère le
cookie via `GET /auth/csrf/` puis renvoie l'en-tête `X-CSRFToken`. L'en-tête
`Authorization: Bearer` reste accepté pour les outils de développement et en est dispensé.

`CSRF_TRUSTED_ORIGINS` doit contenir l'origine du frontend, sans quoi toute écriture est rejetée.

### Révocation des sessions

Un access token est sans état : SimpleJWT ne sait révoquer que les refresh tokens. Le champ
`User.token_version` est embarqué dans chaque token et vérifié à chaque requête ; l'incrémenter
invalide instantanément **toutes** les sessions. Il est incrémenté par la déconnexion globale, le
changement de mot de passe, la réinitialisation et la suspension d'un compte. Les refresh tokens
correspondants sont en plus mis en liste noire.

**Changement de mot de passe** : toutes les sessions sont révoquées, puis de nouveaux cookies sont
posés pour l'appareil courant. L'utilisateur reste donc connecté ici et est déconnecté partout
ailleurs — la sémantique de `update_session_auth_hash` de Django.

### Messages et énumération de comptes

Un compte inexistant et un mauvais mot de passe renvoient le même message. Une fois le mot de
passe correct fourni, le demandeur a prouvé qu'il détient le compte : lui indiquer qu'il est en
attente ou suspendu ne divulgue plus rien. `forgot-password` renvoie toujours la même réponse,
que le compte existe ou non et qu'il ait une adresse email ou non.

### Emails

En Docker, les emails partent vers **Mailpit** (http://localhost:8025) : rien n'est envoyé
réellement et le lien de réinitialisation est cliquable depuis l'interface. Hors Docker, ils
s'affichent dans la console. Les envois sont tracés dans `EmailLog`, consultable depuis l'admin,
sans jamais contenir de token ni de mot de passe.

### Validation d'une demande d'inscription

Depuis l'admin (`/admin/accounts/registrationrequest/`, actions « Accepter » / « Refuser ») ou en
ligne de commande :

```bash
docker compose exec backend python manage.py accept_registration_request <username>
```

```bash
docker compose exec backend python manage.py reject_registration_request <username>
```

## Objectifs nutritionnels

### Calcul calorique

Le calcul est déterministe et **exclusivement côté backend** : le frontend affiche le résultat
mais ne le recalcule jamais. Il repose sur **Mifflin-St Jeor**, un coefficient d'activité et un
delta de `rythme × 1100` kcal par jour (1 kg de masse grasse ≈ 7 700 kcal). La formule complète,
les coefficients et les seuils d'avertissement sont documentés dans `specs/01-functional-specs.md`
§3 et implémentés dans [calculation.py](backend/nutrition/services/calculation.py).

Chaque estimation porte la mention imposée : « Il s'agit d'une estimation et non d'une
recommandation médicale. » Les valeurs jugées déraisonnables déclenchent un avertissement **sans
jamais bloquer** la saisie ; seuls l'âge inférieur à 18 ans et une incohérence entre l'objectif et
le poids cible sont refusés.

### Historique et non-rétroactivité

Créer un objectif ne modifie pas le précédent : il le clôt à la veille de la nouvelle période. Un
objectif passé garde donc ses valeurs pour toujours. La base garantit qu'une seule période reste
ouverte et que les périodes ne se chevauchent pas.

Des surcharges par jour de la semaine permettent un objectif différent le samedi, par exemple ; un
champ laissé vide reprend la valeur de l'objectif de base.

En cas d'incohérence entre les macros et les calories, **les calories font foi** : l'écart est
signalé dans `macro_calories_gap`, jamais corrigé silencieusement.

### Onboarding

Après sa première connexion, l'utilisateur est redirigé vers `/onboarding` et ne peut pas accéder
à l'application avant de l'avoir terminé. Le parcours compte 7 étapes (profil, objectif, activité,
rythme, calories, macros, résumé) et n'écrit qu'à la fin, en une seule transaction.

## Aliments

### Import de la table Ciqual

Le jeu de données n'est pas versionné : trop volumineux et sous licence distincte. Téléchargez-le
sur [ciqual.anses.fr](https://ciqual.anses.fr/) (archive XML), puis :

```bash
docker compose exec backend python manage.py import_ciqual /chemin/vers/ciqual
```

L'import accepte un dossier ou une archive ZIP, lit les 55 Mo de composition en flux et se termine
en quelques secondes pour 3 185 aliments. Il est **idempotent** : le relancer met à jour les fiches
au lieu de les dupliquer. `--sample N` limite l'import pour le développement.

Un extrait réel de 40 aliments est versionné dans `backend/nutrition/tests/fixtures/ciqual` pour
les tests et le parcours E2E.

> **Attribution.** Anses. 2020. Table de composition nutritionnelle des aliments Ciqual. Données
> réutilisables selon la Licence Ouverte, à condition d'indiquer la source et la version.

### Deux pièges du fichier officiel

L'encodage est `windows-1252` et les décimales utilisent la virgule. Surtout, **les fichiers ne
sont pas du XML bien formé** : le texte contient des `<` bruts, dans les noms comme
« Panaché préemballé (<1° alc.) » et dans les milliers de teneurs « < 0,01 ». L'importeur les
échappe à la volée, ligne par ligne, sans quitter le mode flux.

### Inconnu n'est pas zéro

C'est la règle qui décide de la qualité de toute la base (spec 01 §8) :

| Valeur Ciqual | Interprétation | Stockage |
| --- | --- | --- |
| `-` | non mesurée | `NULL`, affiché « — » |
| `traces` | mesurée, négligeable | `0` |
| `< 0,01` | mesurée sous le seuil | `0` |

La vitamine A n'est pas publiée telle quelle : elle est reconstituée en équivalents rétinol,
`rétinol + bêta-carotène / 6`, selon la convention européenne.

### Recherche

À partir de deux caractères, insensible à la casse et aux accents, tolérante aux fautes : « pate »
trouve « Pâté », « poulets » trouve « Poulet ». Tout est résolu par PostgreSQL en une requête, avec
un index GIN trigramme sur un texte désaccentué — environ 10 ms sur les 3 185 aliments.

Le classement suit l'ordre de la spec 01 §7 : favoris, récents, fréquents, correspondance exacte,
correspondance par préfixe, similarité, puis pondération de source.

### Permissions

| Source | Lecture | Écriture |
| --- | --- | --- |
| Ciqual | tout compte actif | admin, désactivation uniquement |
| Aliment personnel (propriétaire) | oui | CRUD complet |
| Aliment personnel partagé à tous | tout compte actif | jamais |
| Aliment personnel privé | propriétaire seul | propriétaire seul |

Un utilisateur ne corrige jamais une fiche officielle ni celle d'un autre : il en crée sa propre
version. Une portion ajoutée sur un aliment global reste privée à son auteur.

## Tests, lint et typecheck

### Backend

```bash
cd backend
pytest                    # tests
ruff check .              # lint
ruff format .             # formatage
ruff format --check .     # vérification du formatage (CI)
```

### Frontend

```bash
cd frontend
npm run test              # Vitest
npm run lint              # ESLint
npm run format            # Prettier
npm run format:check      # vérification du formatage (CI)
npm run typecheck         # tsc --noEmit
npm run build             # build de production
```

### Bout en bout (Playwright)

Deux parcours : cycle de vie du compte (inscription → validation → connexion → onboarding →
route privée → déconnexion) et aliments (recherche → fiche → favori → création). Playwright démarre
lui-même le backend et un build servi en statique.

```bash
cd frontend
npx playwright install chromium   # une seule fois
npm run test:e2e
```

Il utilise la base de développement (`docker compose up -d db redis` suffit) et supprime les
comptes qu'il crée. La validation administrateur passe par la commande de gestion réelle : aucune
route de test n'est exposée par l'application.

La CI GitHub Actions (`.github/workflows/ci.yml`) exécute l'ensemble sur `develop`, `main` et
sur chaque pull request.

## Variables d'environnement

`.env.example` (racine) est exhaustif et documenté. Il alimente docker compose **et** le
backend lancé hors Docker. Le frontend a son propre `frontend/.env` car Vite ne lit que les
fichiers d'environnement de sa propre racine.

| Groupe | Variables |
| --- | --- |
| Django | `DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `APP_VERSION` |
| Données | `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| Redis / Celery | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| URLs | `FRONTEND_URL`, `BACKEND_URL` |
| CORS / CSRF | `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` |
| Cookies d'auth | `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_DOMAIN`, `AUTH_COOKIE_REFRESH_PATH` |
| Mot de passe | `PASSWORD_RESET_TIMEOUT` (durée du lien de réinitialisation, en secondes) |
| IA | `AI_ENABLED`, `ANTHROPIC_API_KEY`, `AI_MEAL_SCAN_MODEL`, `AI_MEAL_PLANNER_MODEL`, `AI_VOICE_PARSING_MODEL`, `AI_RECIPE_MODEL` |
| Email | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` |
| Stockage S3 | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` |
| Uploads | `MAX_UPLOAD_SIZE_MB` |
| Ports Docker | `BACKEND_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `MAILPIT_UI_PORT`, `MAILPIT_SMTP_PORT` |
| Frontend | `VITE_API_BASE_URL` (dans `frontend/.env`) |

Les variables IA et S3 sont déclarées et lues, mais aucune fonctionnalité ne les utilise encore.

## Structure du dépôt

```text
myfitnesspalworld/
├── backend/
│   ├── config/            # settings (base/local/production/test), urls, celery, wsgi
│   ├── accounts/          # User, demandes d'inscription, profil, API auth
│   │   ├── services/      # inscription, sessions et cookies
│   │   └── management/    # accept_/reject_registration_request
│   ├── nutrition/         # objectifs, calcul calorique, onboarding, aliments et recherche
│   ├── progress/          # suivi du poids
│   ├── notifications/     # EmailLog et service d'envoi d'emails
│   ├── common/            # health check, format d'erreur, pagination, permissions
│   ├── nutrition/ diary/ recipes/ planning/ social/ progress/ ai/ notifications/
│   ├── requirements.txt   # dépendances épinglées
│   └── pyproject.toml     # configuration Ruff et pytest
├── frontend/
│   ├── src/
│   │   ├── lib/           # client API (refresh silencieux, CSRF), QueryClient
│   │   ├── components/    # ui (shadcn), layout, formulaires, thème
│   │   ├── features/      # auth, account, onboarding, goals, foods, settings, health
│   │   └── pages/         # écrans publics et privés
│   ├── e2e/               # parcours Playwright
│   └── public/            # icônes PWA
├── specs/                 # spécifications — source de vérité
├── .github/workflows/
├── docker-compose.yml
└── .env.example
```

### Choix techniques du socle

- **Authentification** : JWT en cookies `HttpOnly`, CSRF appliqué, révocation réelle par
  `token_version`. Voir la section [Authentification](#authentification).
- **Permissions** : DRF refuse par défaut (`IsAuthenticated`) ; chaque endpoint public doit
  s'ouvrir explicitement. `IsActiveAccount` filtre en plus sur le statut du compte.
- **Erreurs d'API** : format unique `{"code", "message", "errors"}`, traduit côté frontend en
  `ApiError` et remonté à l'utilisateur par un toast global.
- **PostgreSQL** : extensions `pg_trgm` et `unaccent` activées dès le socle pour la future
  recherche d'aliments.
- **Icônes PWA** : placeholders générés (silhouette simple sur fond bleu), à remplacer par le
  logo définitif.

## Conventions

Branches : `develop` (développement) et `main` (production).

Commits — [Conventional Commits](https://www.conventionalcommits.org/) :

```text
feat(scope): description
fix(scope): description
refactor(scope): description
test(scope): description
docs(scope): description
chore(scope): description
perf(scope): description
```

Avant un commit significatif : tests, lint, typecheck, vérification des migrations, absence de
secret, permissions, et mise à jour des specs si le comportement public change.

## Spécifications

Les règles métier écrites dans `specs/` font foi. Une règle non définie ne doit pas être
inventée silencieusement.

| Fichier | Contenu |
| --- | --- |
| `specs/00-overview.md` | vision, périmètre, architecture générale |
| `specs/01-functional-specs.md` | règles fonctionnelles détaillées |
| `specs/02-user-flows.md` | parcours utilisateurs principaux |
| `specs/03-data-model.md` | modèle de données cible |
| `specs/04-api.md` | catalogue d'API DRF |
| `specs/05-permissions-security.md` | permissions, sécurité, confidentialité |
| `specs/06-frontend-ux.md` | React, navigation, responsive, design |
| `specs/07-ai-integrations.md` | Meal Scan, Voice Logging, Meal Planner |
| `specs/08-tests-quality.md` | tests, qualité et définition de fini |
| `specs/09-deployment-railway.md` | déploiement production Railway |
| `specs/10-coding-rules.md` | conventions de code, Git et migrations |
| `specs/11-external-data-sources.md` | Ciqual, Open Food Facts, USDA |

`CLAUDE.md` contient les instructions de travail destinées à Claude Code.
