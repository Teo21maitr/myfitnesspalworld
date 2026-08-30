# Déployer sur Railway, pas à pas

Ce document se suit **dans l'ordre**, une fenêtre Railway à côté. Chaque étape se
termine par une vérification : si elle échoue, ne passe pas à la suivante — la
cause est toujours plus facile à trouver là où elle apparaît.

Le [README](../README.md#mise-en-production) sert de référence une fois le
déploiement fait ; ici, c'est la séquence.

> **Trois choses ne sont pas dans ce dépôt et n'y seront jamais** : ton compte
> Railway, tes secrets, ton domaine. Aucune clé n'a besoin de passer par un
> fichier versionné.

---

## Avant de commencer

Il te faut :

- un compte Railway et un moyen de paiement (le plan gratuit ne suffit pas pour
  six services qui tournent en continu) ;
- un nom de domaine, ou l'acceptation d'utiliser les sous-domaines
  `*.up.railway.app` que Railway génère ;
- un fournisseur d'emails SMTP — Resend, Brevo, Mailgun, ou le SMTP de ton
  hébergeur. **Sans lui, la réinitialisation de mot de passe ne fonctionne pas**,
  et le backend refusera de démarrer plutôt que de faire semblant ;
- la branche `main` à jour. Elle existe et la CI y est verte.

Prépare dès maintenant une clé secrète Django, que tu colleras à l'étape 3 :

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Ne la garde nulle part ailleurs que dans Railway.

---

## 1. Le projet et la base de données

1. **New Project** → **Deploy from GitHub repo** → choisis `myfitnesspalworld`.
2. Railway crée un premier service. Ignore-le pour l'instant, il servira de
   backend à l'étape 3.
3. Dans le projet : **New** → **Database** → **Add PostgreSQL**.
4. **New** → **Database** → **Add Redis**.

Note le **nom exact** des deux services (par défaut `Postgres` et `Redis`) : tu
vas les référencer, et une majuscule compte.

> **Vérification.** Les deux bases affichent un statut actif et exposent une
> variable `DATABASE_URL` / `REDIS_URL` dans leur onglet *Variables*.

---

## 2. Régler la source du service backend

Sur le service créé à l'étape 1, onglet **Settings** :

| Réglage | Valeur |
| --- | --- |
| Service Name | `backend` |
| Root Directory | `/backend` |
| Branch | `main` |

Les commandes de démarrage, le healthcheck et le `migrate` de pré-déploiement
sont déclarés dans `.railway/railway.ts` — tu les appliqueras à l'étape 5, une
fois les trois services backend créés. En attendant, laisse ces champs vides
dans l'interface.

---

## 3. Les variables du backend

Onglet **Variables** du service `backend`. Colle celles-ci telles quelles :

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<la clé générée plus haut>
DJANGO_ALLOWED_HOSTS=.up.railway.app

# Références entre services : ne recopie pas les valeurs, elles changent.
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# Provisoires : on les corrigera à l'étape 7, une fois les URL connues.
FRONTEND_URL=https://exemple.invalid
BACKEND_URL=https://exemple.invalid
CORS_ALLOWED_ORIGINS=https://exemple.invalid
CSRF_TRUSTED_ORIGINS=https://exemple.invalid

# Emails. Adapte à ton fournisseur.
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp de ton fournisseur>
EMAIL_PORT=587
EMAIL_HOST_USER=<identifiant>
EMAIL_HOST_PASSWORD=<mot de passe>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=MyFitnessPalworld <bonjour@ton-domaine.fr>

# Open Food Facts exige un contact identifiable (spec 11 §3).
OFF_CONTACT_EMAIL=<ton email>
```

Trois remarques qui évitent des heures de recherche.

**`${{Postgres.DATABASE_URL}}` est une référence**, pas une chaîne à recopier.
Railway la résout au déploiement ; une valeur copiée deviendrait fausse à la
première rotation d'identifiants.

**Ne définis pas `PORT`.** Railway l'injecte, et l'image l'utilise.

**`FRONTEND_URL` et `BACKEND_URL` sont provisoirement invalides.** Elles ne
peuvent pas l'être *vides* : le backend refuse de démarrer sans elles, parce
qu'un lien de réinitialisation vers `localhost` partirait sans que rien ne le
signale. On les corrige à l'étape 7.

---

## 4. Premier déploiement

Déclenche un déploiement (**Deploy** ou un push sur `main`).

Suis les journaux. Tu dois voir, dans l'ordre : la construction de l'image, le
`migrate` de pré-déploiement, puis gunicorn qui démarre.

Puis **Settings → Networking → Generate Domain**. Note l'URL obtenue, du type
`backend-production-xxxx.up.railway.app`.

> **Vérification.** Deux appels, et les deux comptent :
>
> ```bash
> curl -s https://<ton-backend>/health/
> curl -s -o /dev/null -w '%{http_code}\n' https://<ton-backend>/admin/login/
> ```
>
> Le premier doit rendre `{"status": "ok", ...}` avec `database` et `cache` à
> `ok`. Le second doit rendre **200**.
>
> Le second n'est pas redondant. Le healthcheck reste vert même si les fichiers
> statiques manquent ; c'est la page d'admin, et elle seule, qui le révèle. La
> CI fait exactement ces deux appels pour cette raison.

**Si le déploiement échoue au démarrage**, lis le message : il nomme la variable
manquante et dit ce qu'elle évite. C'est prévu.

---

## 5. Le worker et le beat

Deux services de plus, depuis le même dépôt et la même racine `/backend`. Ils ne
diffèrent que par leur fichier de configuration.

Pour chacun : **New** → **GitHub Repo** → `myfitnesspalworld`, puis **Settings** :

| | `celery-worker` | `celery-beat` |
| --- | --- | --- |
| Root Directory | `/backend` | `/backend` |
| Branch | `main` | `main` |
| Domaine public | **aucun** | **aucun** |

Copie les **mêmes variables** qu'à l'étape 3 dans chacun des deux services. Le
plus simple est le *Shared Variables* du projet : définis-les une fois au niveau
projet, et référence-les depuis les trois services.

Ne leur donne **aucun domaine public** : ils n'écoutent rien.

### Puis appliquer les commandes de démarrage

Les trois services backend partagent la racine `/backend`. Sans instruction
contraire, **les trois lanceraient gunicorn** : c'est la commande de l'image. Un
worker qui lance un serveur web ne traite aucune tâche, et rien ne le signale.

Ces commandes vivent dans `.railway/railway.ts`, à la racine du dépôt. Depuis
ton poste :

```bash
railway link
```

```bash
railway config plan
```

Il doit annoncer trois modifications : la commande de démarrage de chaque
service, plus le healthcheck et le `migrate` du backend. Puis :

```bash
railway config apply
```

> **Pourquoi un fichier et non trois.** Railway a déprécié `railway.json`, qui
> se plaçait à la racine de chaque service — et refuse désormais de déployer un
> projet qui en contient. Le format actuel décrit tous les services dans un
> **unique** `.railway/railway.ts`, ce qui règle au passage le problème de la
> racine partagée : chaque service y a sa commande, même quand trois pointent
> vers le même dossier.
>
> Les variables restent en `preserve()` : elles vivent dans Railway, et aucun
> secret n'entre dans le dépôt.

> **Vérification.** Les journaux du worker affichent `celery@... ready.` et la
> liste des tâches. Ceux du beat affichent son planificateur, avec
> `send-due-reminders` et `purge-expired-async-tasks`.
>
> S'ils affichent des lignes de gunicorn, la configuration n'a pas été
> appliquée : reprends `railway config plan`.

---

## 6. Le frontend

**New** → **GitHub Repo** → `myfitnesspalworld`, puis **Settings** :

| Réglage | Valeur |
| --- | --- |
| Service Name | `frontend` |
| Root Directory | `/frontend` |
| Branch | `main` |

Une seule variable, et c'est la plus piégeuse du déploiement :

```bash
VITE_API_BASE_URL=https://<ton-backend>/api/v1
```

> **Elle est figée dans le bundle.** C'est une variable de **construction**, pas
> d'exécution : la changer plus tard n'a aucun effet tant que le frontend n'est
> pas **reconstruit**. Retiens-le pour l'étape 7.
>
> Si elle n'arrive pas jusqu'à la construction, celle-ci **échoue** avec un
> message explicite plutôt que de produire un bundle qui appellerait
> `localhost`. C'est délibéré : après la construction, ce défaut n'est plus
> rattrapable.

Puis **Settings → Networking → Generate Domain**.

> **Vérification.** Ouvre l'URL du frontend, puis **recharge la page sur une
> route profonde** — `/journal` par exemple. Elle doit afficher l'application et
> non un 404 : c'est le repli SPA de nginx.
>
> La connexion échouera encore, et c'est normal : le backend refuse ce domaine.
> Étape suivante.

---

## 7. Croiser les URL, puis reconstruire

C'est ici que tout se relie. Tu as maintenant deux URL réelles.

Retourne dans les variables du **backend** (et du worker, et du beat) et remplace
les quatre valeurs provisoires :

```bash
FRONTEND_URL=https://<ton-frontend>
BACKEND_URL=https://<ton-backend>
CORS_ALLOWED_ORIGINS=https://<ton-frontend>
CSRF_TRUSTED_ORIGINS=https://<ton-frontend>,https://<ton-backend>
DJANGO_ALLOWED_HOSTS=<ton-backend sans https://>
```

Puis, dans le **frontend**, vérifie que `VITE_API_BASE_URL` pointe bien sur le
backend et **déclenche une reconstruction** — un simple redémarrage ne suffit
pas, l'adresse est dans le bundle.

Deux cookies méritent une attention si tes deux services sont sur des domaines
**différents** (`backend-xxx.up.railway.app` et `frontend-xxx.up.railway.app` en
sont) :

```bash
AUTH_COOKIE_SAMESITE=None   # déjà la valeur par défaut en production
AUTH_COOKIE_SECURE=True     # idem
```

Si tu passes plus tard sur `api.ton-domaine.fr` et `app.ton-domaine.fr`, tu
pourras revenir à `Lax` et poser `AUTH_COOKIE_DOMAIN=.ton-domaine.fr`.

> **Vérification.** Ouvre le frontend, va sur **Demande d'inscription** et
> envoie-la. Elle doit aboutir. Si l'onglet réseau montre une erreur CORS, l'une
> des quatre variables ci-dessus ne correspond pas exactement — protocole
> compris.

---

## 8. Le premier compte, et les aliments

Depuis l'onglet **Shell** du service backend, ou en local avec la CLI Railway :

```bash
python manage.py createsuperuser
```

Puis les aliments — sans eux, la recherche ne renvoie rien :

```bash
python manage.py import_ciqual <chemin de l'archive Ciqual>
```

L'archive se télécharge sur le site de l'ANSES ; la commande accepte une archive
ou un dossier.

Enfin, valide ta propre demande d'inscription depuis
`https://<ton-backend>/admin/` — ou par la commande :

```bash
python manage.py accept_registration_request <ton nom d'utilisateur>
```

> **Vérification.** Connecte-toi, termine l'onboarding, cherche « poulet » et
> ajoute-le au journal.

---

## 9. Wait for CI

**Settings → Source → Wait for CI**, sur les trois services backend et sur le
frontend.

Sans ce réglage, Railway déploie dès le push, sans attendre GitHub Actions : un
commit qui casse les tests partirait en production avant que quiconque le sache.

> **Vérification.** Pousse un commit anodin sur `main` et observe : le
> déploiement doit rester en attente jusqu'à ce que la CI passe au vert.

---

## 10. Sauvegardes

Sur le service PostgreSQL : active les **sauvegardes automatiques**.

Puis **éprouve une restauration**. Une sauvegarde qu'on n'a jamais restaurée est
une sauvegarde dont on ignore si elle fonctionne — c'est exactement le genre de
certitude qui s'effondre au pire moment.

---

## 11. Ce qui reste facultatif

Ces trois blocs peuvent attendre : sans eux, la fonctionnalité concernée répond
proprement `503` et le reste de l'application n'en souffre pas.

**Les photos de progression** demandent un stockage objet S3 — Railway en
propose, sinon Backblaze B2 ou Scaleway conviennent. Le seau doit être **privé** :

```bash
S3_ENDPOINT_URL=https://<endpoint>
S3_PUBLIC_ENDPOINT_URL=https://<endpoint>   # si le navigateur voit une autre adresse
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
S3_REGION=...
```

`S3_PUBLIC_ENDPOINT_URL` n'est utile que si le backend et le navigateur joignent
le stockage par des adresses différentes. Chez un fournisseur public, elles sont
identiques et tu peux l'omettre.

**L'IA** (scan de repas, lecture d'étiquette, planification) :

```bash
AI_ENABLED=True
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
AI_MEAL_SCAN_MODEL=...
AI_LABEL_SCAN_MODEL=...
AI_MEAL_PLANNER_MODEL=...
```

**Le préchargement HSTS**, une fois le domaine stabilisé et pas avant :

```bash
SECURE_HSTS_PRELOAD=True
```

La liste est embarquée dans les navigateurs ; en sortir prend des mois.

---

## Dépannage

| Symptôme | Cause la plus probable |
| --- | --- |
| Le conteneur s'arrête au démarrage | Une variable obligatoire manque. Le message la nomme et dit ce qu'elle évite |
| `/health/` répond 503 | `DATABASE_URL` ou `REDIS_URL` mal référencée. Le corps de la réponse dit laquelle |
| `/health/` vert mais l'admin en 500 | Les fichiers statiques manquent. L'image les construit : vérifie que le build a bien utilisé l'étage `production` |
| Erreur CORS dans le navigateur | `CORS_ALLOWED_ORIGINS` ne correspond pas exactement à l'origine du frontend, protocole compris |
| 403 CSRF à la connexion | `CSRF_TRUSTED_ORIGINS` incomplet, ou cookies bloqués : vérifie `AUTH_COOKIE_SAMESITE=None` sur deux domaines distincts |
| Le frontend appelle `localhost` | `VITE_API_BASE_URL` posée après la construction. Reconstruis |
| La construction du frontend échoue | `VITE_API_BASE_URL` absente. C'est la garde qui parle, et elle a raison |
| Aucun email n'arrive | Le backend refuse de démarrer avec un backend email muet ; s'il démarre, le problème est chez le fournisseur SMTP |
| Les rappels ne partent pas | Le service `celery-beat` ne tourne pas, ou tourne en plusieurs exemplaires |
| 404 sur une route rechargée | Le repli SPA de nginx : le frontend n'a pas été construit avec son étage `production` |

---

## Après

Le README décrit ce que fait chaque garde-fou et pourquoi. La
[spec 09](../specs/09-deployment-railway.md) porte l'architecture visée et la
checklist de production.

Et quand tu voudras une notification sur ton téléphone plutôt que dans
l'application, il restera à brancher le push : la colonne `push_enabled` attend
son canal depuis l'étape 18.
