# 09 — Déploiement Railway

Ce document décrit le déploiement cible de MyFitnessPalworld avec **un environnement local et un environnement production**.

Les interfaces Railway peuvent évoluer : si un libellé diffère, suivre la documentation Railway officielle actuelle.

## 1. Architecture production

```text
GitHub main
    │
    ├── GitHub Actions
    │   ├── backend lint/tests
    │   ├── frontend lint/typecheck/tests
    │   └── frontend build
    │
    └── Railway Wait for CI
            │
            ├── frontend
            ├── backend
            ├── celery-worker
            ├── celery-beat
            ├── PostgreSQL
            ├── Redis
            └── object storage S3-compatible
```

Seuls frontend et backend ont besoin d'être accessibles publiquement.
Postgres et Redis restent privés.

## 2. Git

Branches :

```text
develop
main
```

`develop` :

- développement local ;
- aucun déploiement Railway obligatoire.

`main` :

- production ;
- push direct autorisé ;
- Railway autodeploy branch = `main`.

Convention commits :

```text
feat(scope): ...
fix(scope): ...
refactor(scope): ...
test(scope): ...
docs(scope): ...
chore(scope): ...
perf(scope): ...
```

## 3. Créer le repository GitHub

1. Créer un repository `myfitnesspalworld`.
2. Pousser le monorepo.
3. Vérifier que `.env` est ignoré.
4. Conserver `.env.example`.
5. Ajouter les workflows GitHub Actions.
6. Tester qu'un push sur `develop` exécute les checks.
7. Tester qu'un push sur `main` exécute les mêmes checks.

## 4. GitHub Actions

Créer par exemple :

```text
.github/workflows/ci.yml
```

Déclenchement :

```yaml
on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [main, develop]
```

Jobs minimum :

### backend

- checkout ;
- setup Python ;
- install ;
- PostgreSQL/Redis de test si requis ;
- `ruff check`;
- tests pytest.

### frontend

- setup Node ;
- `npm ci`;
- ESLint ;
- Prettier check ;
- `tsc --noEmit`;
- Vitest ;
- `npm run build`.

## 5. Créer le projet Railway

1. Se connecter à Railway.
2. Créer un nouveau projet.
3. Choisir le repository GitHub.
4. Utiliser l'environnement `production` par défaut.
5. Ne pas créer de staging permanent.

## 6. Ajouter PostgreSQL

Dans le canvas Railway :

1. Add/Create.
2. Database.
3. PostgreSQL.

Le backend reçoit une `DATABASE_URL` ou les variables PG de Railway.

Django doit lire les secrets via environnement.

Activer les sauvegardes production.

Prévoir périodiquement un test de restauration.

## 7. Ajouter Redis

Ajouter Redis.

Utilisation :

- broker Celery ;
- résultats/statuts si retenu ;
- cache éventuel.

Variable :

```text
REDIS_URL
```

## 8. Backend service

Créer un service connecté au même repo.

Root directory :

```text
/backend
```

Variables :

```text
DJANGO_SECRET_KEY=
DJANGO_SETTINGS_MODULE=
DATABASE_URL=
REDIS_URL=

FRONTEND_URL=
BACKEND_URL=

ANTHROPIC_API_KEY=
AI_MEAL_SCAN_MODEL=
AI_MEAL_PLANNER_MODEL=
AI_VOICE_PARSING_MODEL=
AI_RECIPE_MODEL=

EMAIL_HOST=
EMAIL_PORT=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=

S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET_NAME=
S3_REGION=
```

Ajouter les variables exactes requises par l'implémentation.

Start command typique :

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Adapter `config` au vrai module Django.

Pre-deploy :

```bash
python manage.py migrate
```

Éventuellement :

```bash
python manage.py collectstatic --noinput
```

si le backend sert des statiques admin via WhiteNoise.

Configurer :

- `DEBUG=False`;
- `ALLOWED_HOSTS`;
- `CSRF_TRUSTED_ORIGINS`;
- CORS allowlist ;
- cookies Secure ;
- HSTS après validation du domaine.

Ajouter endpoint health :

```text
GET /health/
```

## 9. Celery worker

Créer un second service depuis le même repo `/backend`.

Même variables que Django nécessaires.

Start command :

```bash
celery -A config worker -l info
```

Adapter le nom de module.

Pas de domaine public.

## 10. Celery Beat

Créer un troisième service backend.

Start command :

```bash
celery -A config beat -l info
```

Pas de domaine public.

Il gère notamment :

- rappels ;
- notifications planifiées ;
- nettoyage fichiers temporaires ;
- refresh cache externe.

## 11. Frontend

Créer un service connecté au repo.

Root directory :

```text
/frontend
```

Variables build/runtime selon l'implémentation, par exemple :

```text
VITE_API_BASE_URL=https://api.example.com/api/v1
```

Build :

```bash
npm ci && npm run build
```

Le mode exact de serving peut être :

- Railway static hosting/config actuelle ;
- ou un petit serveur statique.

Le frontend doit gérer le fallback SPA vers `index.html`.

## 12. Domaines

Exemple :

```text
app.example.com  → frontend
api.example.com  → backend
```

Configurer DNS selon les instructions Railway.

Puis ajuster :

```text
FRONTEND_URL
BACKEND_URL
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
CORS_ALLOWED_ORIGINS
```

## 13. Wait for CI

Pour le service frontend et les services backend liés à `main` :

1. connecter la branche `main` ;
2. activer autodeploy ;
3. activer **Wait for CI** ;
4. vérifier que le workflow GitHub contient bien un trigger `push` sur `main`.

Résultat :

- push direct `main` autorisé ;
- GitHub Actions démarre ;
- Railway attend ;
- tests échouent → pas de nouveau déploiement ;
- tests passent → déploiement.

## 14. Migrations

Règles :

- migration pré-déploiement ;
- échec migration = déploiement échoué ;
- ne jamais modifier une migration déjà appliquée ;
- préférer migrations backward-compatible ;
- éviter en une seule release une suppression de colonne encore utilisée par l'ancienne version.

Pour les migrations risquées :

1. sauvegarde ;
2. migration additive ;
3. déploiement code ;
4. migration cleanup dans une release ultérieure.

## 15. Création superuser

Après premier déploiement backend :

utiliser Railway shell/CLI ou commande one-off appropriée :

```bash
python manage.py createsuperuser
```

Ne jamais mettre le mot de passe admin dans le repository.

## 16. Import CIQUAL

Après création base :

```bash
python manage.py import_ciqual <fichier>
```

Le nom réel de commande sera défini par l'implémentation.

L'import doit être idempotent ou documenter clairement sa stratégie d'upsert.

## 17. Object storage

Photos progression :

- bucket privé ;
- stockage permanent ;
- URLs signées temporaires.

Meal Scan/audio :

- temporaires ;
- suppression après traitement.

PDF :

- temporaire ;
- suppression après expiration ou téléchargement selon implémentation.

## 18. Backups

Production PostgreSQL :

- activer snapshots/backup Railway ;
- prévoir sauvegardes logiques périodiques si souhaité ;
- documenter une procédure `pg_dump` / `pg_restore` ;
- tester une restauration avant de considérer les backups fiables.

Avant migration sensible : lancer/valider un backup.

## 19. Rollback

En cas de problème :

1. identifier dernier déploiement stable ;
2. utiliser redeploy/rollback Railway selon fonctionnalités disponibles ;
3. vérifier compatibilité schema BDD ;
4. ne jamais restaurer la BDD sans comprendre les écritures survenues depuis.

Les migrations destructives rendent les rollbacks plus dangereux : les éviter.

## 20. Checklist production

- [ ] `DEBUG=False`
- [ ] secret key unique
- [ ] Postgres production
- [ ] Redis
- [ ] migrations appliquées
- [ ] admin accessible et protégé
- [ ] frontend HTTPS
- [ ] backend HTTPS
- [ ] CORS strict
- [ ] CSRF strict
- [ ] cookies Secure/HttpOnly
- [ ] stockage privé
- [ ] backups activés
- [ ] healthcheck
- [ ] GitHub Actions vert
- [ ] Railway Wait for CI
- [ ] aucune clé dans Git
- [ ] imports nutritionnels faits
- [ ] tests reset email
- [ ] tests notifications push
- [ ] test Meal Scan
- [ ] test suppression fichiers temporaires
- [ ] test restauration backup

## 22. Ce que le dépôt déclare

Ajouté à l'étape 19, pour que le déploiement ne repose pas seulement sur des réglages saisis dans
une interface :

- `.railway/railway.ts` — le projet entier dans un fichier : les quatre services, leurs commandes,
  le healthcheck `/health/` et le pré-déploiement `migrate`. Railway a déprécié les `railway.json`
  par service, que cette spec décrivait implicitement, et refuse de déployer un dépôt qui en
  contient. Le format unique règle au passage la racine partagée : les trois services backend
  pointent vers `/backend` et gardent chacun sa commande. Les variables y sont en `preserve()` :
  elles vivent dans Railway.
- `docs/deploiement-railway.md` — la marche à suivre, étape par étape, avec une vérification à
  chaque palier.
- `backend/Dockerfile` en trois étages. `production` n'installe **pas** `requirements-dev.txt`, pose
  `DJANGO_SETTINGS_MODULE=config.settings.production` — un oubli donne alors la production, jamais
  le développement — et exécute `collectstatic` **à la construction** plutôt qu'au pré-déploiement,
  qui s'oublie.
- `frontend/Dockerfile` et `frontend/nginx.conf.template` — le bundle est servi par nginx, avec
  repli SPA vers `index.html`. `VITE_API_BASE_URL` est un argument de construction : elle est figée
  dans le bundle, et `vite.config.ts` refuse de construire sans elle.
- Un job `deploy` dans la CI : `check --deploy` en `--fail-level WARNING`, construction des deux
  images, **démarrage réel** du backend, puis `/health/` et une page d'admin. Seule la seconde
  prouve que le manifeste statique existe.

`production.py` refuse par ailleurs de démarrer sans `FRONTEND_URL`, `BACKEND_URL`,
`DEFAULT_FROM_EMAIL`, ni avec un `EMAIL_BACKEND` qui ne remet rien à personne : leurs valeurs de
développement produisent un comportement plausible plutôt qu'une erreur.

## 21. Sources officielles utiles

Railway :

- https://docs.railway.com/guides/django
- https://docs.railway.com/deployments/github-autodeploys
- https://docs.railway.com/databases/postgresql
- https://docs.railway.com/guides/postgres-backups-restores
- https://docs.railway.com/deployments
- https://docs.railway.com/overview/production-readiness-checklist
