# MyFitnessPalworld

PWA mobile-first de suivi alimentaire et nutritionnel, à usage privé.

Ce dépôt est un monorepo : un backend Django/DRF, un frontend React/Vite, et le corpus de
spécifications qui fait foi pour toutes les règles métier.

> **État actuel : socle technique.** L'application démarre, le frontend communique avec le
> backend, la qualité et la CI sont en place. Les fonctionnalités métier (journal, aliments,
> recettes, planner, social, IA) ne sont pas encore implémentées.

## Sommaire

- [Prérequis](#prérequis)
- [Installation](#installation)
- [Lancement avec Docker](#lancement-avec-docker)
- [Lancement hors Docker](#lancement-hors-docker)
- [Migrations](#migrations)
- [Superutilisateur](#superutilisateur)
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

Six services démarrent : `db` (PostgreSQL 17), `redis` (Redis 8), `backend` (Django),
`worker` et `beat` (Celery), `frontend` (Vite). Les migrations sont appliquées
automatiquement au démarrage du backend.

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| API | http://localhost:8001/api/v1/ |
| Health check | http://localhost:8001/health/ |
| Admin Django | http://localhost:8001/admin/ |

> **Ports décalés.** Les ports par défaut sont 8001 (API), 5433 (PostgreSQL) et 6380 (Redis)
> pour cohabiter avec d'autres projets qui occupent souvent 8000 et 5432. Ils sont
> configurables par `BACKEND_PORT`, `POSTGRES_PORT`, `REDIS_PORT` et `FRONTEND_PORT`.

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
| Cookies d'auth | `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_DOMAIN` |
| IA | `AI_ENABLED`, `ANTHROPIC_API_KEY`, `AI_MEAL_SCAN_MODEL`, `AI_MEAL_PLANNER_MODEL`, `AI_VOICE_PARSING_MODEL`, `AI_RECIPE_MODEL` |
| Email | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` |
| Stockage S3 | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` |
| Uploads | `MAX_UPLOAD_SIZE_MB` |
| Ports Docker | `BACKEND_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `REDIS_PORT` |
| Frontend | `VITE_API_BASE_URL` (dans `frontend/.env`) |

Les variables IA, email et S3 sont déclarées et lues, mais aucune fonctionnalité ne les
utilise encore.

## Structure du dépôt

```text
myfitnesspalworld/
├── backend/
│   ├── config/            # settings (base/local/production/test), urls, celery, wsgi
│   ├── accounts/          # modèle User personnalisé, admin, authentification cookie
│   ├── common/            # health check, format d'erreur, pagination, permissions
│   ├── nutrition/ diary/ recipes/ planning/ social/ progress/ ai/ notifications/
│   ├── requirements.txt   # dépendances épinglées
│   └── pyproject.toml     # configuration Ruff et pytest
├── frontend/
│   ├── src/
│   │   ├── lib/           # client API, QueryClient, utilitaires
│   │   ├── components/    # ui (shadcn), layout, thème
│   │   ├── features/      # code par domaine métier
│   │   └── pages/
│   └── public/            # icônes PWA
├── specs/                 # spécifications — source de vérité
├── .github/workflows/
├── docker-compose.yml
└── .env.example
```

### Choix techniques du socle

- **Authentification** : JWT en cookies `HttpOnly` (`CookieJWTAuthentication`), access 15 min,
  refresh 30 jours, rotation et blacklist activées. Aucun token n'est stocké dans
  `localStorage`. Les endpoints `/auth/` ne sont pas encore implémentés.
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
