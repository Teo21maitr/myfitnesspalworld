# MyFitnessPalworld

PWA mobile-first de suivi alimentaire et nutritionnel, à usage privé.

Ce dépôt est un monorepo : un backend Django/DRF, un frontend React/Vite, et le corpus de
spécifications qui fait foi pour toutes les règles métier.

> **État actuel : comptes, objectifs, aliments, journal, progression, recettes, social et
> courses.** Un utilisateur peut demander un compte, être accepté, se connecter, dérouler
> l'onboarding, obtenir un objectif calorique calculé, rechercher parmi les 3 185 aliments de la
> table Ciqual, scanner un code-barres, tenir son journal alimentaire, copier une journée vers
> d'autres dates, suivre son poids et ses mensurations, composer des recettes et des repas
> enregistrés, se lier d'amitié, partager, générer sa liste de courses, et faire reconnaître un
> repas sur une photo. Le planner, les rapports, l'analyse et la saisie vocale restent à faire.

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
- [Produits de marque et code-barres](#produits-de-marque-et-code-barres)
- [Journal alimentaire](#journal-alimentaire)
- [Accueil et copie](#accueil-et-copie)
- [Progression](#progression)
- [Recettes et repas enregistrés](#recettes-et-repas-enregistrés)
- [Amis et partage](#amis-et-partage)
- [Liste de courses](#liste-de-courses)
- [Scanner un repas et le socle IA](#scanner-un-repas-et-le-socle-ia)
- [Créer un aliment depuis son étiquette](#créer-un-aliment-depuis-son-étiquette)
- [Planification des repas](#planification-des-repas)
- [Une seule navigation](#une-seule-navigation)
- [Analyse et rapports](#analyse-et-rapports)
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
| `diary/0001_initial` | `MealType`, `DiaryDay`, `DiaryEntry` |
| `diary/0002_alter_diaryentry_meal_type` | suppression de compte : `meal_type` en cascade |
| `progress/0002_bodymeasuremententry` | `BodyMeasurementEntry` |
| `recipes/0001_initial` | `Recipe`, `RecipeIngredient`, `RecipeNutrition`, `SavedMeal`, `SavedMealItem` |
| `diary/0003_diaryentry_recipe` | clé `recipe` sur `DiaryEntry` |
| `social/0001_initial` | `FriendRequest`, `Friendship`, `SharePermission` |
| `planning/0001_initial` | `ShoppingList`, `ShoppingListItem` |
| `social/0002_alter_sharepermission_resource_type` | la liste de courses devient partageable |
| `common/0002_app_settings_and_async_tasks` | `AppSetting`, `AsyncTask` |
| `ai/0001_initial` | `AITaskLog` |
| `accounts/0004_usersettings_food_search_languages` | langues de recherche de produits |
| `common/0003_alter_asynctask_task_type` | type de tâche « lecture d'étiquette » |
| `ai/0002_alter_aitasklog_task_type` | le même type, côté trace d'appel |
| `planning/0002_mealplan_mealplanday_mealplanentry_and_more` | `MealPlan`, `MealPlanDay`, `MealPlanEntry` |
| `common/0004`, `ai/0003` | type de tâche « génération de plan » |

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

## Produits de marque et code-barres

Ciqual ne contient que des aliments génériques : « pâte à tartiner » y figure, « Nutella » non.
Les produits emballés viennent d'[Open Food Facts](https://world.openfoodfacts.org/), interrogée
par code-barres et mise en cache localement.

### Scanner

`/scanner` lit le code-barres avec l'API `BarcodeDetector` du navigateur quand elle existe, et
sinon avec ZXing, chargé à la demande — Safari et Firefox ne proposent pas l'API native, donc sur
iPhone le repli est le cas normal. La bibliothèque reste dans un chunk séparé et n'alourdit pas le
bundle principal. **La saisie manuelle du code est toujours disponible**, y compris si la caméra
est refusée ou absente.

Un code inconnu de toutes les sources mène au formulaire de création, code-barres prérempli.

### Ordre de résolution

1. aliment personnel de l'utilisateur portant ce code ;
2. cache local des produits déjà rapatriés ;
3. Open Food Facts ;
4. sinon création manuelle.

Une fiche en cache depuis plus de 30 jours est rafraîchie par une tâche Celery : l'utilisateur
reçoit la donnée en cache immédiatement, sans attendre le réseau.

### Quotas — le point à ne pas manquer

Open Food Facts limite **par adresse IP** : 15 requêtes par minute pour la lecture de produits,
10 pour la recherche. Le backend ne présentant qu'une adresse, ce quota est partagé par tous les
comptes. Deux étages le protègent : un throttling par utilisateur, et un budget global dans Redis
qui empêche tout appel sortant une fois épuisé.

C'est pourquoi la recherche texte sur Open Food Facts n'est **jamais** déclenchée à la frappe :
elle demande un clic explicite sur « Chercher sur Open Food Facts ».

`OFF_ENABLED=False` coupe la source sans redéploiement ; la recherche locale, Ciqual et les
aliments personnels continuent de fonctionner normalement.

### Langues de recherche, et ce qu'elles ne corrigent pas

Open Food Facts indexe le nom des produits **par langue**. Chercher uniquement en français rend
donc invisibles les produits nommés ailleurs — alors que le scan de code-barres, lui, n'a jamais eu
cette restriction : on trouve un produit suédois en scannant son emballage, mais pas en tapant son
nom. Les langues sont un réglage par compte, dans « Mon compte », `fr` et `en` par défaut. Ajouter
le suédois double environ le nombre de résultats : `filmjölk` passe de 24 à 45.

**La couverture, elle, ne se règle pas.** Elle varie fortement selon les pays :

| Enseigne | Produits référencés |
| --- | --- |
| ICA — premier distributeur suédois | 1 461 |
| Garant | 804 |
| Änglamark | 153 |
| Carrefour, U, Auchan | ≥ 10 000 chacun |

Un produit absent de la source reste absent quelle que soit la langue interrogée. La réponse est la
création manuelle, avec le code-barres prérempli.

### Trois pièges de conversion

Vérifiés sur des produits réels, chacun couvert par un test :

| Piège | Détail |
| --- | --- |
| Énergie | `energy_100g` est en kJ (2252 pour le Nutella), `energy-kcal_100g` en kcal (539) |
| Unités | les micronutriments sont en **grammes** (`calcium_100g = 0.148`), le modèle en mg et µg |
| Portions | `nutrition_data_per` peut valoir `serving` ; seules les clés `_100g` sont lues |

Les valeurs aberrantes — la base est collaborative — sont écartées plutôt que tronquées, et les
fiches importées ne sont jamais marquées « vérifiées ».

> **Attribution.** Données issues d'Open Food Facts, sous licence ODbL. Une revue de licence
> s'impose avant toute diffusion publique, la base étant combinée avec Ciqual.

## Journal alimentaire

Le journal est le point d'arrivée de tout le reste : c'est là qu'un aliment cherché, scanné ou
créé devient une consommation.

### Le snapshot porte les valeurs de référence

Une entrée n'enregistre pas « 288 kcal consommées », mais les valeurs **pour la quantité de
référence** de l'aliment — 100 g le plus souvent — accompagnées de la quantité et de l'unité :

```text
consommé = snapshot_energy_kcal × (quantité convertie ÷ snapshot_reference_amount)
```

Enregistrer directement le total rendrait impossible la modification ultérieure de la quantité :
il faudrait retourner interroger l'aliment source, qui a pu changer ou disparaître. Avec les
valeurs de référence, une entrée vieille de six mois se recalcule depuis elle seule.

C'est ce qui réconcilie les deux exigences de la spec : le journal reste modifiable dans le passé
(spec 01 §5) et une modification de la source ne touche jamais l'historique (spec 01 §6).

Le facteur de l'unité est figé lui aussi. Sans cela, une portion supprimée rendrait l'entrée
incalculable.

### Toutes les unités ne sont pas calculables

La spec 01 §9 interdit toute conversion millilitres ↔ grammes sans densité connue. Les unités
proposables dépendent donc de l'unité de référence de l'aliment :

| Référence | Unités acceptées |
| --- | --- |
| `g` | g, kg, portions ayant un équivalent en grammes |
| `ml` | ml, cl, cuillère à café, cuillère à soupe, portions en millilitres |
| `unit` | unité, portions ayant un équivalent en unités |

Une cuillère est une mesure de volume : la proposer sur un aliment exprimé en grammes
reviendrait à inventer une densité. L'API expose `available_units` sur chaque fiche, pour que
l'interface ne propose jamais une unité que le backend refuserait.

### Totaux partiels

Un nutriment qu'aucune entrée ne renseigne reste inconnu. Quand certaines entrées le
renseignent et d'autres non, le total est affiché mais **signalé comme partiel** : l'ignorer
reviendrait à compter les inconnues pour zéro.

### Repas

Les quatre repas par défaut sont créés **par utilisateur**, à sa première visite. Chacun peut les
renommer, les réordonner et les désactiver sans affecter les autres comptes. Supprimer un repas
système, ou un repas contenant déjà des entrées, le désactive au lieu de l'effacer.

### Suppression de compte

Les clés du journal sont en cascade : supprimer un compte emporte ses journées, ses repas et ses
entrées, quel que soit le chemin — API, admin Django ou shell.

Une contrainte `PROTECT` sur le repas avait été essayée d'abord, pour interdire qu'un repas
disparaisse sous ses entrées. Elle rendait toute suppression de compte impossible : le collecteur
de Django rencontre la protection avant d'avoir supprimé quoi que ce soit. La garantie de ne pas
perdre d'historique vit donc dans le service `meal_types.remove()`, qui désactive un repas déjà
utilisé au lieu de le supprimer.

## Accueil et copie

### Copier n'est pas figer

Deux règles cohabitent, et les confondre donnerait des valeurs fausses sans que rien ne le
signale.

**Modifier** une entrée corrige une consommation passée : son snapshot fait foi, et l'aliment
source peut avoir changé depuis, cela ne la touche pas.

**Dupliquer** une entrée déclare une nouvelle consommation : elle repart des **valeurs actuelles**
de l'aliment (spec 01 §5). L'implémentation naïve — recopier la ligne en base — porterait des
valeurs périmées.

Quand l'aliment a disparu ou n'est plus visible, la copie retombe sur le snapshot stocké. Refuser
ferait échouer la copie d'une journée entière à cause d'un seul produit supprimé.

Les horaires sont conservés, seule la date change. Une copie **s'ajoute** : la journée cible garde
ce qu'elle contenait déjà.

### Ce qui se copie

| Action | Portée |
| --- | --- |
| Dupliquer | une entrée, dans la même journée ou ailleurs |
| Copier ce repas | un repas vers une ou plusieurs dates, éventuellement vers un autre repas |
| Copier la journée | toutes les entrées, chacune retrouvant son repas |
| Ajouter sur plusieurs dates | un même aliment, une même quantité |

Le déplacement entre repas passe par un menu et non par un glisser-déposer : la spec 06 §6 exige
qu'un geste ne soit jamais l'unique moyen d'agir, et un menu reste utilisable au clavier comme au
lecteur d'écran.

### Tableau de bord

`GET /dashboard/?date=` renvoie la même journée que `GET /diary/`, enrichie du poids. Les deux
passent par le même service : ils ne peuvent pas afficher deux totaux différents pour une même
date.

Le jeu de widgets est fixe — calories, macros, repas, poids, raccourcis. `dashboard_config` existe
en base si la personnalisation vient plus tard. Le bloc « notifications importantes » de la
spec 04 §16 n'est pas renvoyé : le modèle `Notification` n'existe pas encore, et une absence vaut
mieux qu'un champ simulé.

Chaque widget reste juste quand la donnée manque : pas d'objectif, aucune pesée, aucun poids
cible. Ce sont les cas d'un compte neuf, pas des cas rares.

## Progression

`GET|POST /progress/weight/` et `GET|POST /progress/measurements/` tiennent l'historique, une
entrée par date. Une seconde saisie sur une date existante **met à jour** au lieu d'échouer sur la
contrainte d'unicité (spec 01 §19) ; l'interface l'annonce avant l'envoi, faute de quoi le
remplacement passerait pour une donnée perdue.

Les six mensurations sont facultatives une par une, mais une entrée qui n'en porte aucune est
refusée : elle ne créerait qu'une ligne vide. Une mesure absente reste `null`, jamais `0`.

### Une moyenne mobile calendaire, pas positionnelle

C'est le seul calcul de cet écran dont une erreur ne se voit pas. Moyenner « les sept dernières
pesées » paraît juste et ne l'est pas : on ne se pèse pas tous les jours, et pour qui se pèse une
fois par semaine cette moyenne couvre **sept semaines**. Elle lisserait un trimestre en le
présentant comme une tendance hebdomadaire, sans que rien ne le signale.

La fenêtre porte donc sur les mesures dont la date tombe dans `[d - 6 jours, d]`, quel qu'en soit
le nombre. Sur des pesées à J-30, J-25, J-3 et J-1, chaque point vaut sa propre mesure ou presque —
une fenêtre positionnelle afficherait 80,83 kg à J-3 là où la bonne réponse est 79,00.

Le lissage remonte au-delà du début de la période demandée : sans ce recul, la moyenne d'une même
date changerait selon qu'on regarde trente ou quatre-vingt-dix jours.

### La courbe

`GET /progress/charts/?from=&to=&metric=` renvoie la série entière de l'intervalle. Endpoint
distinct de `/progress/weight/`, qui est **paginé à 25** : trois mois de pesées quotidiennes
dépassent la première page, et une courbe bâtie dessus serait tronquée sans le dire. La période
vaut 90 jours par défaut et ne peut excéder deux ans, pour que la réponse reste finie.

`metric` accepte `weight`, `waist`, `hips`, `chest`, `arm`, `thigh` et `body_fat`. Seul le poids
porte une cible, reprise du profil. `trend_per_week` est une régression linéaire sur les mesures
réelles — la calculer sur la moyenne mobile surpondérerait les périodes de pesée dense — et vaut
`null` sous deux points : `0` affirmerait une stagnation constatée.

Le graphique est un SVG écrit à la main, sans dépendance. Son axe des abscisses est **temporel** :
un axe ordinal ferait paraître identiques deux jours et trois semaines, et un trou de vacances
ressemblerait à une progression régulière. Aucun point n'est fabriqué pour les jours sans mesure.

Les photos de progression (spec 01 §20) demandent le stockage objet, non configuré : elles ne
figurent pas encore sur cet écran.

## Recettes et repas enregistrés

Une **recette** rassemble des ingrédients préparés ensemble puis divisés en portions
(spec 01 §14). Un **repas enregistré** est un raccourci : un ensemble d'aliments et de recettes
déjà portionnés (spec 01 §13). Les deux vivent dans l'app `recipes`.

### Une entrée de recette emprunte la forme de l'ajout rapide

Le snapshot du journal porte une quantité de référence et son unité — 100 g le plus souvent. Une
portion de blanquette n'est ni des grammes ni des millilitres : elle se **compte**. L'entrée
reprend donc exactement la forme de l'ajout rapide, déjà en place depuis l'étape 6 — référence
d'une portion, unité `unit`, facteur figé à 1 — et son snapshot porte les valeurs **par portion**.
Aucun nouveau type d'unité n'a été nécessaire.

Une recette ajoutée au journal produit **une seule** entrée, pas une par ingrédient : c'est le plat
qui a été mangé. Un repas enregistré, lui, **se déplie** en entrées normales et indépendantes, que
l'on peut ensuite modifier ou supprimer une à une.

### Le piège : la copie devait apprendre une troisième nature

L'étape 7 avait posé la règle : une copie repart de la version **actuelle** de la source, l'entrée
d'origine garde son snapshot. `copy_entry` l'appliquait en interrogeant l'aliment — et commençait
par `if entry.food_id is None: return None`.

Une entrée de recette n'a pas de `food_id`. Sans correction, elle serait tombée dans le repli prévu
pour les sources disparues, et sa copie aurait porté l'**ancienne** version de la recette. Aucun
test existant ne l'aurait vu : ils ne couvraient que les aliments et les ajouts rapides. L'écran
aurait affiché un nombre plausible.

Le contrôle qui tranche, sur la vraie base : journaliser deux portions d'une recette à 200 kcal,
doubler ensuite un ingrédient, puis dupliquer l'entrée. La copie doit porter 800 kcal et
l'originale 400. Un `copy_entry` ignorant les recettes en aurait donné 400 aux deux.

### Nutrition d'une recette

Le cache porte les vingt nutriments et non les seules macros : le snapshot du journal les exige
tous. Il est calculé **par portion**, puisque c'est ce qui s'affiche et ce qui se recopie.

La règle « inconnu n'est pas zéro » n'est pas réécrite ici : elle vit dans
`nutrition/services/aggregation.py`, partagée avec le journal. Un nutriment qu'un seul ingrédient
ne renseigne pas donne un total partiel, signalé par `incomplete_nutrients` et présenté comme tel
à l'écran.

Le cache peut se périmer **sans que la recette bouge** : c'est l'aliment qui change. La lecture
compare donc la date du dernier changement d'ingrédient à celle du calcul, et recalcule si besoin.
L'annotation est posée sur le queryset entier pour qu'une page de vingt-cinq recettes ne déclenche
pas vingt-cinq agrégats.

### Un ingrédient dont l'aliment disparaît

`Food.owner` est en cascade : supprimer un compte efface ses aliments, y compris ceux qu'il avait
partagés. Un ingrédient les référençant passe alors à `NULL` plutôt que de disparaître — son nom
est conservé à l'ajout, la ligne reste lisible, et la nutrition de la recette devient partielle.
La faire disparaître aurait allégé la recette en silence.

Le même choix vaut pour un élément de repas enregistré : il est **nommé dans `skipped`** au moment
de l'ajout au journal, sans empêcher les autres d'y entrer.

### Champs nutritionnels partagés

`FoodNutrition` et `RecipeNutrition` décrivent les mêmes vingt nutriments. Ils héritent d'un modèle
abstrait `NutrientValues` : aucune table, aucune migration, et deux jeux de colonnes qui ne peuvent
plus diverger — ce qui compte, puisque le journal recopie l'un ou l'autre dans le même snapshot.

## Amis et partage

Se chercher par nom d'utilisateur, s'inviter, accepter, puis partager aliments personnels,
recettes, repas enregistrés, journal et progression (spec 01 §17 et §18). Le partage à des
personnes précises suppose une amitié : c'est ce qui donne au retrait d'ami quelque chose à
révoquer.

Jusqu'à cette étape, quatre endroits du code portaient la même promesse — « `SPECIFIC_USERS`
existe dans le modèle mais n'est pas encore applicable ». Elle est tenue.

### Un partage ne survit jamais à sa raison d'être

C'est le seul endroit de cette fonctionnalité où une erreur ne se voit pas. Un accès accordé
légitimement puis conservé après la disparition de ce qui le justifiait ne lève aucune exception,
n'apparaît nulle part à l'écran, et laisse lire des données privées. Trois chemins y mènent :

- **le retrait d'ami** — la spec 01 §17 exige la révocation, donc `remove_friend()` supprime
  l'amitié **et** les permissions dans la même transaction. Effacer la ligne d'amitié seule
  laisserait l'ancien ami lire le journal comme avant ;
- **la suspension** — la spec 05 §2 rend inaccessibles les partages d'un compte suspendu. Or
  `IsActiveAccount` ne contrôle que l'appelant : les filtres de visibilité vérifient donc aussi
  l'état du **propriétaire** ;
- **la confusion de type** — `SharePermission` porte `resource_type` *et* `resource_id`. Les
  identifiants sont propres à chaque table : la recette 42 et l'aliment 42 coexistent, et
  n'interroger que l'identifiant ferait d'un partage de recette un accès à un aliment.

Le contrôle qui tranche, sur la vraie base : deux comptes amis, trois partages, puis retrait.
Il ne doit rester **aucune** `SharePermission` entre eux, et l'ex-ami perdre la recette, le
journal et la progression d'un coup.

### Des routes séparées, jamais un paramètre

La consultation partagée vit sous `/shared/` et ne fait que lire. Ajouter un `user_id` aux
endpoints du propriétaire aurait fait servir « mes données » ou « celles d'un autre » à la même
route selon un paramètre — la façon canonique de fabriquer un IDOR, puisqu'il suffit d'oublier
une vérification sur un chemin.

Ces vues n'écrivent aucune logique : `build_day(user, day)` et `charts.series(user, …)` étaient
déjà paramétrés par l'utilisateur. Elles vérifient le partage, puis appellent le service existant
avec le propriétaire. Les totaux ne peuvent donc pas diverger selon qui regarde.

Un partage absent répond **404 et non 403** : dire qu'une ressource existe mais reste fermée
renseignerait déjà sur les données d'autrui.

Côté interface, les écrans partagés ne proposent **aucune** action d'écriture. Le backend
refuserait, mais offrir une action vouée au refus est déjà un défaut.

### Ce que `resource_id` nul veut dire

Le journal et la progression ne sont pas des lignes : ce sont l'ensemble des journées et des
mesures de leur propriétaire (spec 05 §8). Leur partage porte donc un `resource_id` nul, et le
fournir est refusé. Les deux partages sont **distincts** : ouvrir son journal n'ouvre pas sa
progression.

Les photos de progression ne figurent pas parmi les types partageables et ne doivent jamais y
figurer (spec 01 §20).

### Amitié bidirectionnelle

`Friendship` stocke le couple sous forme canonique — le plus petit identifiant d'abord — avec une
contrainte de base qui l'impose. Sans elle, A→B et B→A pourraient coexister et « sommes-nous
amis ? » n'aurait pas de réponse unique.

Une demande émise vers quelqu'un qui vous a déjà invité vaut acceptation.

Une demande d'ami n'émet aucune notification : le modèle `Notification` (spec 01 §24) n'existe
pas encore. L'entrée « Amis » de la barre latérale porte une pastille tant que des demandes
attendent.

## Liste de courses

Générée depuis des recettes ou des journées, complétée à la main, cochée en faisant les courses,
et partageable comme le reste (spec 01 §16).

### Regrouper n'est pas additionner

« 150 g poulet + 300 g poulet = 450 g poulet » se lit comme une addition. Ce n'en est pas une :
les quantités portent des unités. 150 g et 1 kg du même poulet se regroupent bien, mais leur somme
vaut **1150 g, pas 151** — un nombre plausible, faux d'un facteur sept, et qu'aucun écran ne
signale. On s'en aperçoit devant l'étal.

Chaque quantité est donc convertie dans l'unité de référence de son aliment, par le même
`resolve_factor()` qui sert au journal, avant d'être sommée.

**Et ce qui ne se convertit pas ne se regroupe pas.** Des millilitres sur un aliment mesuré en
grammes, une portion supprimée entre-temps : la ligne reste séparée plutôt qu'approximée
(spec 01 §9). Deux lignes valent mieux qu'une somme inventée.

Un article ajouté à la main ne fusionne jamais automatiquement : son auteur l'a écrit tel quel, et
l'absorber dans une quantité générée le ferait disparaître de sa liste.

### Ce qu'une journée verse au panier

Une entrée d'aliment donne son aliment. Une entrée de **recette** est dépliée en ingrédients, mis
à l'échelle des portions consommées : deux portions d'une recette qui en fait quatre versent la
moitié de ses ingrédients. On n'achète pas des portions de blanquette.

Un ajout rapide n'apporte rien : il n'a pas d'aliment à mettre au panier.

### Une liste est un brouillon

Sa suppression est franche, sans suppression douce : rien ne la référence, et la spec 01 §16 exclut
tout historique automatique. C'est le seul modèle du projet qui se supprime vraiment.

`quantity` et `unit_label` sont nullables : « du sel » est un article valable, et inventer
« 1 unité » serait une donnée qu'on n'a pas.

### La règle de visibilité, écrite une fois

La liste de courses aurait été la quatrième copie du même filtre — à soi, ouvert à tous par un
propriétaire actif, ou partagé nommément. Quatre copies d'une clause de sécurité finissent par
diverger sans que rien ne le signale. La règle vit désormais dans `visibility_filter()`, que les
aliments, les recettes, les repas enregistrés et les listes appellent tous.

L'extraction n'a demandé aucune modification des tests existants — c'est ce qui la distingue d'une
réécriture.

## Scanner un repas et le socle IA

Photographier une assiette, laisser un modèle nommer ce qu'il y voit, corriger, journaliser.

### Ce qu'il faut pour que ça marche

**La fonctionnalité est éteinte tant que trois variables ne sont pas posées.** Sans elles, chaque
appel répond `503 ai_disabled` — c'est correct, et c'est exactement ce qui se produit sur un `.env`
copié avant l'arrivée de l'IA :

```text
AI_ENABLED=True
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=…
```

Puis `docker compose up -d --force-recreate backend worker`. L'écran interroge `GET /ai/status/` à
son ouverture et annonce l'indisponibilité **avant** de faire cadrer une photo : l'apprendre au
moment de l'envoi était le défaut de la première version.

`AI_PROVIDER=fake` remplace le modèle par deux aliments fixes — utile pour travailler l'interface
sans clé. La production refuse cette valeur.

### La prise de vue

La caméra s'ouvre dans la page. `<input type="file" capture>` ne suffisait pas : les navigateurs de
bureau l'ignorent et n'offrent qu'un sélecteur de fichiers.

Le cycle de vie du flux vit dans `useCameraStream`, **partagé avec le lecteur de codes-barres**
plutôt que réécrit à côté. Une caméra ne s'éteint pas parce qu'on a changé d'écran : quatre sorties
doivent l'arrêter — démontage, fermeture explicite, démarrage de l'analyse, et **autorisation
accordée après le départ**, quand `getUserMedia` résout sur un composant démonté. En manquer une
laisse le voyant allumé sans qu'aucune erreur ne le signale.

L'import de fichier reste offert **en permanence**, pas seulement en repli : un geste n'est jamais
l'unique moyen d'agir (spec 06 §6).

### Le modèle propose des mots, la base fournit les calories

Un modèle à qui l'on montre une assiette répond volontiers « Poulet grillé, 150 g, **248 kcal** ».
Le nombre est plausible. Il est inventé.

S'il entrait dans le journal, l'application mentirait sur la seule chose qu'elle existe pour
mesurer — sans écran rouge, sans total aberrant, sans rien qui le signale.

La parade est structurelle, pas disciplinaire. Trois barrières indépendantes :

1. le **schéma JSON** envoyé au fournisseur ne déclare aucune propriété nutritionnelle, et interdit
   tout champ supplémentaire ;
2. le **serializer** de validation ne conserve que les cinq champs attendus — libellé, quantité,
   unité, confiance, alternatives — et écarte le reste ;
3. la **construction du résultat** est explicite : elle recopie ces champs, jamais l'objet reçu.

Le libellé est ensuite cherché dans le référentiel avec la recherche ordinaire, celle du champ de
recherche, et les valeurs affichées sont celles des fiches trouvées.

Le fournisseur simulé renvoie délibérément un `energy_kcal: 9999`. Chaque exécution des tests, et
chaque passage du parcours de bout en bout, prouve donc qu'il n'atteint ni l'écran ni le journal.

### L'endpoint ne journalise rien

`POST /ai/meal-scan/` rend des suggestions et **crée zéro entrée**. C'est `/diary/entries/` qui
écrit, une fois l'utilisateur passé par l'écran de correction — la même route que la recherche
manuelle, qui sait déjà résoudre l'aliment, vérifier l'unité et figer le snapshot.

Une unité que l'aliment retenu ne sait pas convertir est remplacée par son unité de référence, des
deux côtés : le backend l'ajuste sur le candidat par défaut, le frontend le refait à chaque
changement d'aliment. Sans cela, la confirmation échouerait en 400 pour un choix que l'utilisateur
n'a pas fait.

### La photo ne survit pas au traitement

Elle ne peut pas transiter par un fichier temporaire — en production, l'API et le worker sont deux
conteneurs, donc deux systèmes de fichiers — ni par le broker, dont le sérialiseur est JSON.

Elle est déposée dans Redis sous une clé non devinable, avec une durée de vie de dix minutes, et le
worker ne reçoit que la clé. Il la lit une fois puis **la supprime, y compris quand le fournisseur
échoue** ; la durée de vie n'est que le filet pour le worker qui meurt avant.

Aucun octet n'atteint le disque. `AITaskLog` ne conserve que la forme de l'entrée — « 1 image(s),
84 ko » — jamais son contenu, jamais le prompt.

### Ce qu'`AsyncTask` fait que Celery ne fait pas

Le backend de résultats de Celery ignore la notion de propriétaire : un identifiant deviné y
donnerait accès au résultat de n'importe qui. La table applicative existe d'abord pour attacher une
tâche à un compte — `GET /tasks/{id}/` filtre sur le propriétaire et répond **404**, jamais 403.

Elle porte accessoirement une progression que Celery ne modélise pas, et une échéance : passé un
jour, le résultat n'intéresse plus personne et une tâche planifiée nocturne le supprime.

### Couper l'IA sans redéployer

`AI_ENABLED` et `ANTHROPIC_API_KEY` disent si l'IA est *configurée*. Les changer suppose un
redéploiement — ce n'est pas un interrupteur.

Le coupe-circuit de la spec 07 §11 vit en base : le réglage `ai_enabled` d'`AppSetting`, modifiable
depuis l'admin Django, relu à chaque appel. À `false`, l'endpoint répond **503 `ai_disabled`** et
tout le reste de l'application continue de fonctionner.

Le quota `ai` de 30 appels par heure n'est pas une limite produit — la spec 07 §5 veut l'usage
illimité — mais une protection contre une boucle emballée.

### Ajouter un fournisseur, ajouter une tâche

`AIProvider` ne connaît ni aliment ni calorie : il sait envoyer un prompt et rendre du JSON conforme
à un schéma, en utilisant le mécanisme natif de son API. Les schémas métier et leur validation
vivent au-dessus.

Ajouter `OpenAIProvider` sera donc un fichier ; ajouter la saisie vocale ou le planner, une méthode
de service. `AI_PROVIDER` choisit entre `anthropic` et `fake` — cette seconde valeur étant refusée
au démarrage en production.

## Créer un aliment depuis son étiquette

Photographier le tableau nutritionnel plutôt que recopier quinze champs à la main. C'est la
réponse au vrai problème du scan de code-barres : quand Open Food Facts ne connaît pas le produit,
la création manuelle était longue.

### Recopier n'est pas estimer

Le modèle **transcrit** ce qui est imprimé. Ce n'est pas la même chose qu'estimer une assiette, et
la consigne le lui dit en toutes lettres : ne rien calculer, ne rien compléter de mémoire, ignorer
les pourcentages d'apports de référence.

### Non lu n'est pas zéro

C'est la règle qui gouverne l'écran. Un reflet sur la ligne des fibres, un nutriment que le produit
ne déclare pas : chacun ressort `null`. Un zéro enregistré affirmerait que le produit n'en contient
pas, et ce mensonge serait recopié dans chaque snapshot de journal qui suivra (spec 01 §8).

L'écran **nomme** ce qui manque — « la photo n'a pas donné : fibres et sodium » — plutôt que de
laisser un champ vide passer pour un oubli de saisie.

Vérifié contre l'API sur une étiquette suédoise sans ligne « fibres » : les sept autres valeurs
sont lues, l'énergie prise en kcal et non en kJ, et les fibres reviennent nulles.

### La colonne lue décide de tout

Les étiquettes européennes portent obligatoirement une colonne « pour 100 g » ou « pour 100 ml »,
mais beaucoup en ajoutent une « par portion ». Recopier la mauvaise fausse tout d'un facteur trois
sans que rien ne le signale.

Le modèle rend donc la base qu'il a lue. Quand ce n'est ni l'une ni l'autre, **aucune valeur n'est
reprise** — l'identité du produit l'est, et l'écran explique pourquoi les champs sont vides.

### Rien n'est enregistré sans vous

Le brouillon ne fait que préremplir le formulaire de création. C'est l'utilisateur qui valide, et
l'aliment créé lui appartient — privé par défaut, non vérifié (spec 01 §11).

Un code-barres illisible est rendu vide plutôt qu'approximé : un code faux ferait créer un doublon
sous une identité qui n'est pas la sienne.

## Planification des repas

Composer des journées sous contraintes, les relire, les journaliser, en tirer les courses.

### La tolérance se mesure sur les fiches, jamais sur les dires du modèle

Le modèle ne pèse rien. Il propose « riz, 200 g » ; ce que 200 g de ce riz-là valent est dans la
base, et peut s'écarter de son estimation d'un tiers. Un plan validé sur ses propres chiffres
paraît juste, s'affiche juste, et rate l'objectif dès qu'on le journalise.

Le schéma qui lui est envoyé ne comporte donc **aucun champ nutritionnel** — ne pas lui demander de
chiffres est la façon la plus sûre de ne pas s'y fier. Chaque libellé est résolu par la recherche
ordinaire, les totaux sont recalculés à partir des fiches, et la tolérance porte sur eux : ±5 % sur
les calories, ±10 % sur les macros (spec 01 §15).

Hors tolérance, la journée est redemandée avec l'écart mesuré — **trois essais au maximum**, puis le
meilleur résultat assorti d'un avertissement. Sans ce plafond, une journée impossible à satisfaire
appellerait le fournisseur indéfiniment.

### Le modèle compose, le backend dose

C'est ce qui fait tenir les objectifs, et ça n'allait pas de soi.

Un modèle de langage choisit bien **quoi** manger et mal **combien**. Viser à la fois des calories
et trois macronutriments en dosant quinze aliments est une optimisation sous contraintes ; la lui
demander de tête produisait des journées à 20 ou 30 % de la cible, et lui redemander de corriger ne
faisait que déplacer l'erreur — les lipides restaient bloqués à +28 %.

`nutrition/services/fitting.py` fait cette arithmétique-là, exactement et sans modèle : à
composition donnée, une descente par coordonnées cherche les quantités qui approchent au mieux les
quatre cibles, chaque objectif pesant l'inverse du carré de sa tolérance. Les facteurs sont bornés
entre 0,4 et 2,5 — la composition proposée doit rester reconnaissable — et les quantités arrondies
à un pas servable : personne ne pèse 237 g de flocons d'avoine.

Mesuré sur les mêmes contraintes, avant et après :

| | Avant | Après |
| --- | --- | --- |
| Journées dans les tolérances | 0 sur 3 | **3 sur 3** |
| Écart maximal | 34 % | 9 % |
| Durée | 176 s | 48 s |
| Appels au modèle | 9 | 4 |

Ce qui reste hors tolérance après dosage ne se corrige plus par les quantités : c'est la
**composition** qui est en cause. C'est cela qu'on redemande alors au modèle — et c'est une
question à laquelle il sait répondre.

### Une journée à la fois, et pourquoi

Mesuré contre l'API : une semaine demandée en un seul appel dépasse 16 000 jetons de réponse et
revient **tronquée** après plus de deux minutes ; une journée en tient 1 800 en une quinzaine de
secondes.

Le découpage n'est pas qu'une affaire de budget. Il colle aux cibles, qui sont journalières —
`resolve_for_date()` rend déjà la valeur applicable à une date, surcharge de jour de semaine
comprise — et il rend chaque correction locale : un jour hors tolérance se rejoue seul.

Une période est bornée à sept jours. C'est ce que la spec demande, et ce que le temps permet : une
journée coûte jusqu'à une minute quand elle demande ses trois essais.

### Corriger à l'aveugle ne corrige rien

Quand une nouvelle demande est nécessaire, elle donne au modèle **ce que ses quantités valaient
réellement**, macros comprises : « Flocon d'avoine 100 g : 380 kcal, P 13 / G 60 / L 7 ». Sans
cela, il ignore ce que pèse cet aliment-là dans ce référentiel-ci, et corrige au jugé.

Ces valeurs viennent de la base, et c'est toujours la base qui tranche : le modèle n'en devient pas
pour autant source de vérité.

### Une proposition n'est pas un plan

La génération **ne persiste rien**. Le résultat est une proposition ; `POST /meal-plans/`
enregistre ce que l'utilisateur a relu — et crée à ce moment-là, dans la même transaction, les
recettes que le modèle a inventées (spec 07 §8). Une recette dont aucun ingrédient ne se retrouve
en base est écartée et nommée, plutôt qu'enregistrée incomplète.

### L'ajout au journal n'écrase rien

Un repas de la journée cible qui contient déjà des entrées est **nommé**, et rien n'est écrit tant
que l'utilisateur n'a pas confirmé. Confirmé, le plan s'ajoute par-dessus : il ne remplace pas.

Les entrées créées sont indépendantes et snapshotées ; modifier ou supprimer le plan ensuite ne
touche pas ce qui a été journalisé.

## Une seule navigation

La navigation vivait dans **deux listes** : une pour la barre latérale desktop, une pour mobile.
Chaque étape remplissait la première, puis rapiéçait l'accès mobile en glissant un bouton dans
« Mon compte ». Cinq étapes plus tard, « Mes repas » n'était atteignable par aucun geste au doigt,
et « Ajout rapide » par aucun clic. Ce n'était pas un lien oublié : c'était une conception qui
garantissait l'oubli.

[`navigation.ts`](frontend/src/components/layout/navigation.ts) ne porte donc plus qu'**une** liste,
groupée en six sections, rendue deux fois : la barre latérale à partir de `md`, un tiroir en deçà.
La barre du bas garde ses quatre raccourcis et son `+` que la spec 06 §2 fixe — ce sont des
raccourcis vers les écrans du quotidien, pas la navigation, qui vit entièrement dans le tiroir.

Le vrai livrable est le garde-fou :
[`navigation.test.ts`](frontend/src/components/layout/navigation.test.ts) parcourt les routes
déclarées dans [`router.tsx`](frontend/src/router.tsx) et échoue si l'une d'elles n'est atteignable
ni par la navigation, ni par une liste explicite de routes **contextuelles** — une fiche d'aliment
s'ouvre depuis la recherche, pas depuis un menu. Ajouter une page sans la rendre atteignable devient
impossible sans le voir. Le parcours de bout en bout
[`analysis.spec.ts`](frontend/e2e/analysis.spec.ts) complète l'autre moitié : sur un écran de
375 px, il ouvre le tiroir et vérifie que **chaque** destination s'affiche vraiment.

## Analyse et rapports

### Une journée sans entrée n'est pas une journée à zéro

C'est la règle de cette partie, et elle décide de tous les chiffres qu'on y lit.

« Tu as consommé 1 640 kcal par jour cette semaine. » Sur sept jours dont deux non journalisés, ce
chiffre est faux — et il ne se voit pas, parce qu'il est plausible. Diviser par sept revient à
affirmer qu'on n'a rien mangé ces deux jours-là. Diviser par cinq répond à une autre question, et
c'est la bonne : *sur les journées que tu as tenues*, voilà ta moyenne.

Les moyennes portent donc sur les journées journalisées, et
[`daily_totals`](backend/diary/services/analysis.py) ne fabrique aucune journée vide. `logged_days`
et `calendar_days` voyagent ensemble jusqu'à l'écran, qui affiche le dénominateur à côté de la
moyenne. Une période entièrement vide renvoie `null`, jamais zéro.

C'est la règle « inconnu n'est pas zéro » de la spec 01 §8, appliquée à la journée entière.

### Un pourcentage calculé sur un total partiel est partiel

`GET /analysis/food/` classe les aliments par ce qu'ils ont apporté d'un nutriment. Si dix entrées
en portent et que trois ne le renseignent pas, le dénominateur est sous-estimé et **chaque** part
est surévaluée. La réponse porte alors `is_partial` et `unknown_entries`, et l'écran annonce des
minorants plutôt que de laisser croire à cent pour cent.

Le regroupement se fait sur le **nom du snapshot** : c'est ce que l'utilisateur a journalisé, et
cela reste juste pour un aliment supprimé depuis.

### Exports

`POST /reports/csv/` et `POST /reports/pdf/` passent par le même rapport que
`GET /reports/summary/` : la période exportée ne peut pas différer de celle affichée.

Le CSV porte une ligne par journée tenue, une colonne par nutriment, un point décimal et une
cellule **vide** — pas un zéro — pour ce qui n'est pas renseigné.

Le PDF passe par **ReportLab**, dont les polices intégrées rendent les accents sans embarquer de
fichier de police ni dépendre d'une bibliothèque système : ce qui compte pour Railway.

Les deux sont **synchrones**, et c'est une mesure qui l'a décidé, pas une intuition : sur
quatre-vingt-dix jours et trois cent soixante entrées, le rapport se compose en 0,15 s et le PDF
en 0,02 s. Un test mesure cette durée ; le jour où il échouera, le socle de tâches asynchrones est
déjà là.

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

Douze parcours : compte, aliments, code-barres, journal, tableau de bord, recettes, progression,
partage, planification, liste de courses, scan de repas et lecture d'étiquette — les deux derniers avec
une caméra simulée par Chromium. Playwright démarre lui-même le backend et un build servi en
statique.

Le parcours de scan de repas force `AI_PROVIDER=fake` et `CELERY_TASK_ALWAYS_EAGER=True` : l'analyse
devient déterministe et ne réclame ni clé d'API ni worker. Les deux valeurs sont refusées au
démarrage en production.

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
| Open Food Facts | `OFF_ENABLED`, `OFF_PRODUCT_URL`, `OFF_SEARCH_URL`, `OFF_CONTACT_EMAIL`, `OFF_USER_AGENT`, `OFF_CONNECT_TIMEOUT`, `OFF_READ_TIMEOUT`, `OFF_PRODUCT_RATE_PER_MINUTE`, `OFF_SEARCH_RATE_PER_MINUTE`, `OFF_CACHE_TTL_DAYS` |
| IA | `AI_ENABLED`, `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `AI_MEAL_SCAN_MODEL`, `AI_LABEL_SCAN_MODEL`, `AI_MEAL_PLANNER_MODEL`, `AI_VOICE_PARSING_MODEL`, `AI_RECIPE_MODEL` |
| Email | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` |
| Stockage S3 | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` |
| Uploads | `MAX_UPLOAD_SIZE_MB` |
| Ports Docker | `BACKEND_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `REDIS_PORT`, `MAILPIT_UI_PORT`, `MAILPIT_SMTP_PORT` |
| Frontend | `VITE_API_BASE_URL` (dans `frontend/.env`) |

Renseignez `OFF_CONTACT_EMAIL` : Open Food Facts exige un User-Agent identifiant l'application
et un contact, faute de quoi les appels risquent d'être pris pour ceux d'un robot.

`AI_MEAL_SCAN_MODEL` est le seul modèle utilisé à ce stade ; les trois autres attendent leurs
fonctionnalités. Les variables S3 sont déclarées mais pas encore employées.

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
