# 04 — API DRF

Base : `/api/v1/`

Format principal : JSON.
Uploads : multipart.
Exports : fichiers.

Pagination : page/limit, 25 éléments par défaut.

## 1. Auth

```text
POST /auth/register-request/
POST /auth/login/
POST /auth/logout/
POST /auth/refresh/
POST /auth/forgot-password/
POST /auth/reset-password/
POST /auth/logout-all/
GET  /auth/me/
GET  /auth/csrf/
```

`GET /auth/csrf/` pose le cookie CSRF **et rend le jeton** dans son corps,
sous `csrf_token`. Les deux, parce que le cookie seul ne suffit pas dès que
l'interface vit sur un autre domaine que l'API : `document.cookie` ne donne
accès qu'aux cookies du domaine courant. Le navigateur envoie bien celui de
l'API à chaque requête — le serveur le lit —, mais le JavaScript ne peut pas
le recopier dans l'en-tête `X-CSRFToken`. Rien ne le montre en développement,
où l'interface et l'API partagent l'hôte `localhost`.

Rendre le jeton au client n'affaiblit rien : c'est lui qui doit le renvoyer. Ce
que la protection exige, c'est qu'un **autre site** ne puisse pas l'obtenir —
garanti par CORS, cette réponse n'étant lisible que depuis les origines
autorisées.

Un échec de vérification répond 403 avec le code `csrf_failed`, distinct de
`permission_denied`. Le client rejoue alors **une** fois avec un jeton neuf :
un cookie effacé ailleurs rendrait sinon toute écriture impossible jusqu'au
rechargement de la page, tandis qu'un vrai refus d'accès ne doit jamais être
rejoué.

## 2. Profil

```text
GET   /profile/
PATCH /profile/

GET   /profile/settings/
PATCH /profile/settings/

GET   /profile/goals/
POST  /profile/goals/
GET   /profile/goals/{id}/
PATCH /profile/goals/{id}/

GET    /profile/goals/current/
POST   /profile/goals/calculate/
PUT    /profile/goals/{id}/overrides/{weekday}/
DELETE /profile/goals/{id}/overrides/{weekday}/

POST  /profile/onboarding/
```

`POST /profile/onboarding/` soumet le parcours complet de façon
transactionnelle : profil, première pesée et objectif initial. Soit tout
réussit, soit rien n'est écrit. Un second appel est refusé.

`POST /profile/goals/calculate/` renvoie un aperçu du calcul sans rien
persister, afin que le frontend n'ait jamais à dupliquer la formule.

`GET /profile/goals/current/` renvoie l'objectif applicable et les valeurs du
jour, surcharge de jour de semaine appliquée.

`{weekday}` suit la convention Python : 0 pour lundi, 6 pour dimanche.

Créer un objectif clôt le précédent à la veille de la nouvelle période : un
changement n'est jamais rétroactif. Si un objectif commence déjà à la date
demandée, il est mis à jour au lieu d'être dupliqué.

## 3. Foods

```text
GET    /foods/search/?q=poulet&page=1&limit=25
GET    /foods/{id}/
POST   /foods/
PATCH  /foods/{id}/
DELETE /foods/{id}/

GET    /foods/recent/
GET    /foods/frequent/
GET    /foods/favorites/

POST   /foods/{id}/favorite/
DELETE /foods/{id}/favorite/

GET    /foods/{id}/portions/
POST   /foods/{id}/portions/
PATCH  /foods/{id}/portions/{portion_id}/
DELETE /foods/{id}/portions/{portion_id}/

GET    /barcodes/{barcode}/
GET    /foods/external-search/?q=nutella
```

`DELETE /foods/{id}/` effectue une suppression douce : la fiche disparaît des
recherches mais reste disponible pour l'historique du journal.

Une portion créée sur un aliment global appartient à son auteur et n'est
visible que de lui.

`/barcodes/{barcode}/` résout un code dans cet ordre : aliment personnel de
l'appelant portant ce code, cache local des produits déjà rapatriés, puis
Open Food Facts. Un produit inconnu répond 404 avec le code
`product_not_found`, ce qui déclenche la création manuelle côté interface. Une
source injoignable répond 503 `external_source_unavailable` : les deux cas ne
doivent jamais être confondus, sous peine de créer des doublons de produits
existants.

`/foods/external-search/` élargit la recherche à Open Food Facts. Elle n'est
jamais déclenchée à la frappe et ne persiste rien : elle renvoie des candidats
(`code`, `name`, `brand`, `food_id` si déjà en base) parmi lesquels seul celui
qu'ouvre l'utilisateur est mis en cache, via `/barcodes/{code}/`.

Ces deux endpoints ont leur propre quota par utilisateur (`off_barcode`,
`off_search`), doublé d'un budget global partagé : Open Food Facts limite par
adresse IP, donc pour l'ensemble des comptes (spec 11 §3).

La recherche renvoie une liste unique ordonnée avec un champ `source`.

## 4. Diary

```text
GET    /diary/?date=YYYY-MM-DD

POST   /diary/entries/
PATCH  /diary/entries/{id}/
DELETE /diary/entries/{id}/

POST   /diary/entries/{id}/duplicate/
POST   /diary/copy-day/
POST   /diary/copy-meal/
POST   /diary/bulk-add/
```

`GET /diary/` renvoie la journée entière en un appel : objectifs applicables à
la date — surcharge de jour de semaine comprise —, totaux consommés et
restants, puis les repas avec leurs entrées et leurs sous-totaux. Chaque entrée
porte un bloc `computed` calculé côté serveur : le frontend ne refait jamais la
multiplication pour l'affichage définitif.

`incomplete_nutrients` liste les nutriments dont au moins une entrée n'était pas
renseignée. Le total correspondant reste affiché mais doit être présenté comme
partiel : l'ignorer reviendrait à compter les inconnues pour zéro (spec 01 §8).

`POST /diary/entries/` accepte un aliment — `food_id`, `quantity`, `unit_label`
— ou un ajout rapide — `entry_type: "quick_add"` et au moins `energy_kcal`
(spec 01 §12). L'aliment est résolu parmi ceux que l'appelant a le droit de
voir, et l'unité doit figurer dans le champ `available_units` de sa fiche : une
unité non calculable est refusée en 400 plutôt qu'approximée (spec 01 §9).

Modifier l'unité d'une entrée exige que son aliment existe encore. S'il a
disparu, seule la quantité reste modifiable : l'entrée conserve le facteur figé
à l'ajout.

`POST /diary/entries/{id}/duplicate/`, `copy-meal`, `copy-day` et `bulk-add`
partagent une règle : **une copie repart de la version actuelle de l'aliment**,
alors que l'entrée d'origine garde son snapshot (spec 01 §5). Quand l'aliment a
disparu ou n'est plus visible, le snapshot stocké est recopié : refuser ferait
échouer la copie d'une journée entière pour un seul produit supprimé.

Les horaires sont conservés, seule la date change. Une copie **s'ajoute** : la
journée cible garde ce qu'elle contenait.

Exemple `copy-day` :

```json
{
  "source_date": "2026-08-23",
  "target_dates": ["2026-08-24", "2026-08-26"]
}
```

## 5. Meal types

```text
GET    /meal-types/
POST   /meal-types/
PATCH  /meal-types/{id}/
DELETE /meal-types/{id}/
POST   /meal-types/reorder/
```

Les quatre repas par défaut sont créés par utilisateur à sa première visite,
puis lui appartiennent : il peut les renommer, les réordonner et les
désactiver sans affecter les autres comptes.

DELETE d'un type système = désactivation. Un repas contenant déjà des
entrées est désactivé lui aussi : l'historique prime.

## 6. Recipes

```text
GET    /recipes/
POST   /recipes/
GET    /recipes/{id}/
PATCH  /recipes/{id}/
DELETE /recipes/{id}/

POST   /recipes/{id}/duplicate/
POST   /recipes/{id}/favorite/
DELETE /recipes/{id}/favorite/
POST   /recipes/{id}/add-to-diary/
```

`add-to-diary` :

- date ;
- meal_type_id ;
- servings ;
- consumed_at facultatif.

Il crée **une seule** entrée de type `recipe`, pas une par ingrédient : c'est le
plat qui a été mangé. Elle emprunte la forme de l'ajout rapide — référence d'une
portion, comptée en unités — car une portion se compte et ne se pèse pas. Son
snapshot porte les valeurs **par portion**, et la quantité leur nombre.

`GET /recipes/` et `GET /recipes/{id}/` renvoient la nutrition d'une portion,
accompagnée de `incomplete_nutrients` : un nutriment qu'un ingrédient ne
renseigne pas rend le total partiel, jamais nul (spec 01 §8).

Le cache nutritionnel est recalculé à chaque écriture, et **aussi à la lecture
lorsqu'un ingrédient a changé depuis** : sans cela, corriger un aliment
laisserait les recettes qui l'emploient afficher un total faux jusqu'à leur
prochaine modification.

Une unité d'ingrédient que le backend ne sait pas convertir est refusée en 400
plutôt qu'approximée (spec 01 §9).

`DELETE` effectue une suppression douce : la recette disparaît des listes mais
les entrées de journal qui la référencent restent valides.

`duplicate` produit une copie indépendante, appartenant à l'appelant et **privée**
même lorsque l'original était partagé : reprendre une recette pour soi ne doit
pas la republier sans le dire.

## 7. Saved meals

```text
GET    /saved-meals/
POST   /saved-meals/
GET    /saved-meals/{id}/
PATCH  /saved-meals/{id}/
DELETE /saved-meals/{id}/
POST   /saved-meals/{id}/duplicate/
POST   /saved-meals/{id}/add-to-diary/
```

Un élément porte un aliment ou une recette déjà portionné. `add-to-diary` **le
déplie** en entrées de journal normales et indépendantes : un aliment devient
une entrée d'aliment, une recette une entrée de recette. Chacune est snapshotée
pour elle-même et plus rien ne les relie ensuite — modifier ou supprimer le
repas enregistré ne touche pas ce qui a déjà été journalisé.

La réponse renvoie `entries` et `skipped` : un élément dont la source a disparu
est nommé plutôt qu'omis en silence, et n'empêche pas l'ajout des autres — même
arbitrage que la copie d'une journée entière.

## 8. Meal plans

```text
GET    /meal-plans/
POST   /meal-plans/
GET    /meal-plans/{id}/
PATCH  /meal-plans/{id}/
DELETE /meal-plans/{id}/

POST   /meal-plans/generate/
POST   /meal-plans/{id}/regenerate-entry/
POST   /meal-plans/{id}/add-to-diary/
```

`generate` reçoit la période, les repas à remplir et les contraintes de la
spec 01 §15 — allergies, aliments aimés, détestés. Il répond **202** avec une
tâche : la composition dure plusieurs dizaines de secondes.

Le résultat est une **proposition**, et rien n'est persisté. C'est
`POST /meal-plans/` qui enregistre ce que l'utilisateur a relu — et qui crée,
à ce moment-là seulement, les recettes que le modèle a inventées (spec 07 §8).

La composition se fait **une journée à la fois**. Chaque jour a sa propre cible,
surcharge de jour de semaine comprise (spec 01 §4), et une semaine entière
demandée en un appel revient tronquée. Le découpage rend aussi chaque correction
locale : un jour hors tolérance se rejoue seul.

Le modèle ne propose que des **libellés et des quantités** ; le schéma ne prévoit
aucun champ nutritionnel. Chacun est résolu dans le référentiel, les totaux sont
recalculés à partir des fiches, et **c'est sur eux que la tolérance est
mesurée** — ±5 % sur les calories, ±10 % sur les macros.

Les quantités sont ensuite **ajustées par le backend** pour approcher les
objectifs : un modèle choisit bien quoi manger et mal combien, et doser quinze
aliments contre quatre cibles est une arithmétique, pas une intuition. Les
facteurs restent bornés, et les quantités arrondies à un pas servable.

Ce qui reste hors tolérance après ajustement tient à la **composition**, pas aux
quantités : la journée est alors redemandée avec l'écart mesuré, **trois essais
au maximum** ; au-delà, le meilleur résultat sort assorti d'un avertissement
(spec 07 §7).

Une période est bornée à **sept jours** : c'est ce que la spec 01 §15 demande, et
ce que le temps permet.

`add-to-diary` **n'écrase jamais** (spec 01 §15). Un repas de la journée cible
qui contient déjà des entrées est nommé dans `conflicts` et rien n'est écrit ;
avec `confirm`, les entrées s'ajoutent par-dessus sans rien remplacer. Le
dépliage suit la règle des repas enregistrés : un aliment devient une entrée
d'aliment, une recette une entrée de recette, chacune snapshotée pour elle-même.

`regenerate-entry` recompose un seul repas et écrit directement dans le plan :
l'utilisateur l'a demandé sur son propre plan, et un plan n'est pas le journal.
Il ne puise que dans l'existant, une recette inventée ne s'enregistrant qu'à
l'acceptation d'un plan.

## 9. Async tasks

```text
GET /tasks/{id}/
```

Réponse type :

```json
{
  "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
  "task_type": "meal_scan",
  "status": "pending",
  "progress": 20,
  "result": null,
  "error": null,
  "created_at": "2026-08-27T12:00:00Z"
}
```

Statuts :

- pending
- processing
- success
- failed

Une tâche **appartient à quelqu'un**. Le backend de résultats de Celery n'a pas
cette notion : un identifiant deviné y donnerait accès au résultat d'autrui.
D'où une table applicative, un identifiant UUID, et un filtrage par
propriétaire. La tâche d'un autre compte répond **404** et non 403.

Le résultat expire au bout d'un jour : passé ce délai la tâche répond 404, et
une tâche planifiée la supprime.

`error` porte un message destiné à l'utilisateur, jamais une trace technique.

## 10. IA

```text
GET  /ai/status/
POST /ai/meal-scan/
POST /ai/label-scan/
```

`GET /ai/status/` répond `{"enabled": bool}`. Il existe pour que l'interface
annonce l'indisponibilité **avant** de faire cadrer une photo : l'apprendre au
moment de l'envoi, après avoir préparé son cliché, est une mauvaise façon de
l'apprendre. Il ne dit rien du fournisseur, du modèle ni de la présence d'une
clé — ce sont des détails de configuration, pas des informations utilisateur.

`POST /ai/voice-log/` n'existe pas encore : la saisie vocale viendra sur le même
socle.

Les endpoints IA **créent une tâche et rendent des suggestions**. Ils ne créent
jamais d'entrée de journal : le frontend confirme ensuite via
`/diary/entries/`, qui sait déjà résoudre l'aliment, vérifier l'unité et figer
le snapshot.

`meal-scan` reçoit de une à trois images en multipart, sous le champ `images`,
chacune en JPEG, PNG ou WebP et dans la limite de `MAX_UPLOAD_SIZE_MB`. Le type
déclaré ne suffit pas : les premiers octets sont vérifiés (spec 05 §14). Il
répond **202** avec la tâche.

Les images ne sont jamais écrites sur disque. Elles transitent par le cache sous
une clé non devinable, et sont supprimées dès l'analyse terminée — y compris
lorsqu'elle échoue (spec 07 §5).

Une suggestion porte le libellé et la quantité proposés par le modèle, sa
confiance, et des **candidats issus de la base** avec leurs valeurs
nutritionnelles. Le modèle ne fournit aucune valeur nutritionnelle : le schéma
qui lui est envoyé n'en prévoit pas, et la validation écarte ce qui n'y figure
pas (spec 07 §1, §4). Un libellé sans correspondance donne une liste de
candidats vide, jamais une erreur.

Une unité proposée que l'aliment retenu ne sait pas convertir est remplacée par
son unité de référence : la transmettre ferait échouer la confirmation en 400
pour un choix que l'utilisateur n'a pas fait (spec 01 §9).

`label-scan` reçoit une photo d'étiquette nutritionnelle et rend un
**brouillon d'aliment**, jamais un aliment : le formulaire de création est
prérempli, et c'est l'utilisateur qui enregistre (spec 01 §11).

Le modèle **recopie** l'étiquette ; il n'estime rien. Une valeur qu'il n'a pas
lue revient **nulle, jamais zéro** — zéro affirme que le produit n'en contient
pas, ce que seule une étiquette lisible permet de dire (spec 01 §8). La réponse
nomme ces manques dans `unreadable` plutôt que de laisser un champ vide passer
pour un oubli de saisie.

`basis` dit quelle colonne a été lue : `100g`, `100ml`, ou `unknown`. Les
étiquettes européennes portent obligatoirement une colonne pour 100, mais
beaucoup en ajoutent une par portion : recopier la mauvaise fausserait tout
d'un facteur trois. Quand aucune colonne pour 100 n'est trouvée, **aucune
valeur n'est reprise** ; l'identité du produit l'est.

Un code-barres illisible ou implausible est rendu vide plutôt qu'approximé : un
code faux ferait créer un doublon sous une identité qui n'est pas la sienne.

L'IA coupée par un administrateur, non configurée ou sans clé répond **503**
`ai_disabled`. Le reste de l'application n'en est pas affecté (spec 07 §11).

## 11. Shopping lists

```text
GET    /shopping-lists/
POST   /shopping-lists/
GET    /shopping-lists/{id}/
PATCH  /shopping-lists/{id}/
DELETE /shopping-lists/{id}/

POST   /shopping-lists/generate/
POST   /shopping-lists/{id}/items/
PATCH  /shopping-lists/{id}/items/{item_id}/
DELETE /shopping-lists/{id}/items/{item_id}/
```

`generate` peut recevoir :

- `shopping_list_id` facultatif
- `recipe_ids[]`
- `dates[]`

Sans `shopping_list_id`, une liste est créée ; avec lui, elle est complétée et
les articles compatibles fusionnent avec ceux déjà présents.

`meal_plan_id` verse tout ce que le planning prévoit : une entrée de recette y
apporte ses **ingrédients** mis à l'échelle des portions planifiées, comme une
journée de journal.

**Regrouper n'est pas additionner.** Les quantités portent des unités : 150 g et
1 kg du même aliment donnent 1150 g, pas 151. Chaque quantité est convertie dans
l'unité de référence de son aliment avant la somme, et **ce qui ne se convertit
pas reste une ligne séparée** plutôt qu'approximé (spec 01 §9) — millilitres
contre grammes, ou portion supprimée entre-temps.

Une entrée de recette dans une journée verse les **ingrédients** de la recette,
mis à l'échelle des portions consommées : on n'achète pas des portions de
blanquette. Un ajout rapide n'apporte rien, n'ayant pas d'aliment.

`quantity` et `unit_label` peuvent être nuls : « du sel » est un article
valable, et inventer « 1 unité » serait une donnée qu'on n'a pas (spec 01 §8).

Un article ajouté à la main ne fusionne jamais automatiquement : son auteur l'a
écrit tel quel.

`DELETE` d'une liste est une suppression franche — pas d'historique automatique
après suppression (spec 01 §16). Une liste reçue se lit ; cocher un article y
est refusé.

## 12. Friends

```text
GET    /users/search/?q=teo
GET    /friends/
GET    /friend-requests/

POST   /friend-requests/
POST   /friend-requests/{id}/accept/
POST   /friend-requests/{id}/reject/
DELETE /friends/{user_id}/
```

`/users/search/` est partielle, insensible à la casse, et **ne porte jamais sur
l'email** (spec 01 §1). Elle ne renvoie que des comptes actifs, jamais
l'appelant, et n'expose de chaque compte que son nom d'utilisateur et son état
civil.

`GET /friends/` ajoute à chaque ami deux drapeaux : `shares_diary` et
`shares_progress`. Ils ne renseignent pas sur les données de l'ami, mais sur les
**accès de l'appelant** — ses propres `SharePermission` reçues, portée globale
comprise.

Ils existent pour que l'interface n'offre « Son journal » que lorsque le lien
aboutit. Sans eux, le bouton s'affichait pour tous les amis et menait au 404 que
la §13 bis impose ; l'utilisateur lisait une panne là où il n'y avait qu'une
absence de partage. Déduire cette absence du 404 aurait été pire : le même code
couvre le compte suspendu et l'incident serveur.

`/users/search/` ne les porte pas. Elle répond sur des inconnus, et leurs
partages ne la concernent pas.

Une demande émise vers quelqu'un qui vous a déjà invité vaut acceptation :
vouloir la même chose que l'autre, c'est être d'accord.

`DELETE /friends/{user_id}/` n'est pas une simple suppression de ligne. Il
**révoque les partages ciblés dans les deux sens** (spec 01 §17). Les partages
`app_users` survivent : ils ne visaient personne en particulier.

## 13. Shares

```text
GET    /shares/
POST   /shares/
DELETE /shares/{id}/
```

Payload :

```json
{
  "resource_type": "recipe",
  "resource_id": 42,
  "visibility": "specific_user",
  "target_user_id": 8
}
```

Pour `app_users`, une visibilité globale suffit — et `target_user_id` doit alors
être absent : un partage à tous ne vise personne.

`resource_type` accepte `food`, `recipe`, `saved_meal`, `shopping_list`,
`diary` et `progress`. Les photos de progression n'en font pas partie et ne
doivent jamais y entrer (spec 01 §20).

`resource_id` est **nul** pour `diary` et `progress`, et pour eux seuls : le
journal n'est pas une ligne mais l'ensemble des journées de son propriétaire
(spec 05 §8). Le fournir est refusé en 400. Une liste de courses, elle, **en a
un** — l'avoir rangée un temps parmi les ressources sans identifiant rendait
son partage impossible, et le message d'erreur parlait du journal.

`GET /shares/received/` ne liste que les partages **nommés**. Un partage
`app_users` ne vise personne : l'y faire entrer remplirait la page des partages
globaux d'inconnus. Il reste lisible, et se découvre par les drapeaux de
`GET /friends/` (§12).

Le couple `(resource_type, resource_id)` forme la clé de lecture. Les
identifiants sont propres à chaque table : la recette 42 et l'aliment 42
coexistent, et n'interroger que l'identifiant transformerait un partage de
recette en accès à un aliment.

Un partage `specific_user` vers quelqu'un qui n'est pas un ami est refusé : la
spec 01 §17 lie les deux en rendant le retrait d'ami révocateur.

```text
GET /shares/received/
```

Ce qu'on a partagé avec l'appelant. Un partage dont le propriétaire n'est plus
actif n'y figure pas (spec 05 §2).

## 13 bis. Consultation partagée

```text
GET /shared/diary/?user_id=&date=
GET /shared/progress/charts/?user_id=&metric=&from=&to=
GET /shared/progress/weight/?user_id=
```

Routes **distinctes** de celles du propriétaire, et en lecture seule. Ajouter un
`user_id` aux endpoints existants ferait servir « mes données » ou « celles d'un
autre » à la même route selon un paramètre : c'est la façon canonique de
fabriquer un IDOR, il suffit d'oublier une vérification sur un chemin.

Elles passent par les mêmes services que le journal et la progression : les
totaux ne peuvent pas diverger selon qui regarde.

Un partage absent répond 404 et non 403 : dire qu'une ressource existe mais
reste fermée renseignerait déjà sur les données d'autrui.

Le partage du journal et celui de la progression sont **distincts** : ouvrir
l'un n'ouvre pas l'autre.

## 14. Progress

```text
GET    /progress/weight/
POST   /progress/weight/
GET    /progress/weight/{id}/
PATCH  /progress/weight/{id}/
DELETE /progress/weight/{id}/

GET    /progress/measurements/
POST   /progress/measurements/
GET    /progress/measurements/{id}/
PATCH  /progress/measurements/{id}/
DELETE /progress/measurements/{id}/

GET    /progress/charts/?from=...&to=...&metric=weight
```

`POST /progress/measurements/` suit la même règle que la pesée : une entrée par
date, une seconde saisie mettant à jour la précédente. Les six mesures sont
facultatives, mais une entrée qui n'en porte aucune est refusée en 400 ; seules
les mesures présentes dans le corps sont remplacées.

`charts` calcule la moyenne mobile côté backend, sur une fenêtre **calendaire**
de sept jours : les mesures dont la date tombe dans `[d - 6 jours, d]`. Une
fenêtre portant sur les sept dernières mesures couvrirait sept semaines pour qui
se pèse une fois par semaine. Le lissage remonte avant `from`, sans quoi la
moyenne d'une même date dépendrait de la période demandée.

`metric` accepte `weight`, `waist`, `hips`, `chest`, `arm`, `thigh` et
`body_fat` ; `weight` par défaut. Seul le poids porte une cible, reprise du
profil. `trend_per_week` est une régression linéaire sur les mesures réelles,
`null` sous deux points.

La période couvre les 90 derniers jours par défaut et ne peut excéder deux ans.
Contrairement à `/progress/weight/`, paginé à 25, cet endpoint renvoie la série
entière de l'intervalle : une courbe bâtie sur une page serait tronquée sans le
dire.

```json
{
  "metric": "weight",
  "unit": "kg",
  "from": "2026-05-29",
  "to": "2026-08-26",
  "points": [
    { "date": "2026-08-26", "value": "78.00", "moving_average": "79.00" }
  ],
  "target": "70.00",
  "trend_per_week": "-0.35"
}
```

Aucun point n'est produit pour les jours sans mesure : interpoler fabriquerait
des valeurs jamais relevées.

## 15. Progress photos

```text
GET    /progress/photos/
POST   /progress/photos/
GET    /progress/photos/{id}/
PATCH  /progress/photos/{id}/
DELETE /progress/photos/{id}/
DELETE /progress/photos/{id}/files/{photo_id}/
```

`{id}` désigne un **groupe** : la date, et jusqu'à quatre photos. C'est lui qui
porte la note et la pesée du jour, tandis qu'une photo ne porte que son fichier.

Le fichier n'est pas modifié : supprimer/réuploader pour remplacer. Seules les
métadonnées se patchent. La dernière route découle de cette phrase — sans elle,
rien ne permettait de retirer **une** photo d'une date.

`POST` reçoit du multipart : `date`, `notes` et `weight_kg_snapshot`
facultatifs, les fichiers sous `photos` et leurs angles sous `photo_types`,
dans le même ordre. Une date déjà photographiée est **complétée**, pas
remplacée : on revient ajouter le profil après la face. Un angle absent vaut
`other` plutôt que de faire échouer l'envoi — la photo compte plus que son
étiquette, et l'étiquette se corrige.

Chaque photo rendue porte une **URL signée de courte durée**, jamais sa clé de
stockage. La clé est non devinable, donc de fait un secret d'accès : la publier
offrirait une cible à qui l'obtiendrait autrement (spec 05 §10).

L'image est **retraitée côté serveur** avant d'être déposée : redimensionnée et
réencodée en JPEG, **métadonnées EXIF supprimées**. Le client compresse déjà,
mais il n'est jamais la source de vérité — et l'EXIF d'un cliché de téléphone
porte les coordonnées du lieu où il a été pris.

`DELETE` emporte les objets du stockage, pas seulement les lignes : la spec 01
§20 promet une suppression définitive. Il en va de même à la suppression du
compte (spec 05 §11).

Sans stockage objet configuré, `POST` répond **503** `storage_unavailable` : la
fonctionnalité n'est pas branchée, et le reste de l'application n'en est pas
affecté.

Les photos ne sont partageables **sous aucune forme** : aucun type ne les
désigne dans `/shares/`, et un partage `progress` ouvre les courbes et les
pesées d'un ami, jamais ses photos (spec 01 §20).

## 16. Dashboard

```text
GET /dashboard/?date=YYYY-MM-DD
```

Renvoie la même journée que `GET /diary/` — objectifs, totaux, restants et
repas — enrichie du poids : dernière pesée, écart depuis la première, poids
cible et part du chemin parcouru.

Les deux endpoints passent par le même service : ils ne peuvent pas afficher
deux totaux différents pour une même date.

La configuration des widgets et les notifications importantes prévues par la
spec ne sont pas encore renvoyées : le jeu de widgets est fixe et le modèle
`Notification` n'existe pas.

## 17. Reports

```text
GET  /reports/summary/?from=...&to=...
POST /reports/pdf/
POST /reports/csv/
```

`summary` rend la période : les journées **tenues** avec leurs totaux, leur
objectif du jour et la pesée éventuelle, puis les moyennes, le respect de
l'objectif calorique, les aliments les plus caloriques et la série de poids —
celle-là même que `/progress/charts/` produit, moyenne mobile comprise.

**Une journée sans entrée n'est pas une journée à zéro.** Elle n'apparaît pas
dans `days` et n'entre dans aucune moyenne : diviser par la longueur du
calendrier reviendrait à affirmer qu'on n'y a rien mangé, ce qui donnerait un
chiffre plausible et faux. `logged_days` et `calendar_days` sont donc renvoyés
tous les deux, et l'interface affiche le dénominateur à côté de la moyenne.

Une période entièrement vide ne renvoie pas des moyennes nulles mais `null` :
la même règle que les nutriments inconnus (spec 01 §8), appliquée à la journée.

La période couvre 30 jours par défaut et ne peut excéder deux ans — même borne
que les courbes, dont les rapports reprennent la série.

Les deux exports reçoivent `from` et `to`, passent par le **même** rapport que
`summary`, et répondent un fichier attaché.

Le CSV porte une ligne par journée tenue et une colonne par nutriment. Une
valeur inconnue y reste **vide**, jamais `0`, et les décimales emploient le
point : une virgule décalerait les colonnes dans un tableur configuré
autrement.

Les deux exports sont **synchrones**. Sur quatre-vingt-dix jours et trois cent
soixante entrées, la composition du PDF tient en deux dixièmes de seconde :
l'asynchrone que cette spec réservait au « si nécessaire » ne l'est pas encore.
Un test mesure cette durée et échouera si elle dérive.

## 18. Analysis

```text
GET /analysis/food/?from=...&to=...&nutrient=protein
GET /analysis/weekly/?from=...
```

`food` classe les aliments par ce qu'ils ont apporté d'un nutriment, avec leur
part du total. Le regroupement porte sur le **nom du snapshot** : c'est ce que
l'utilisateur a journalisé, et cela reste juste pour un aliment supprimé depuis
(spec 01 §6).

Une entrée qui ne renseigne pas ce nutriment est comptée dans `unknown_entries`
et l'analyse est marquée `is_partial`. Le total additionne alors ce qui est
connu, et **chaque part est un minorant** : le dénominateur est sous-estimé,
donc tous les pourcentages sont surévalués. L'interface doit le dire plutôt que
de laisser croire qu'ils somment à cent.

`nutrient` accepte les vingt champs du référentiel ; `energy_kcal` par défaut.
Un nutriment inconnu est refusé en 400 : les glucides nets, par exemple, sont
une soustraction d'affichage et non une colonne.

`weekly` est le rapport de `/reports/summary/` appliqué aux sept jours qui
suivent `from` — la semaine en cours par défaut. Il passe par le même service :
deux résumés distincts finiraient par afficher deux moyennes pour les mêmes
journées.

## 19. Notifications

```text
GET  /notifications/
POST /notifications/{id}/read/
POST /notifications/read-all/

GET   /notification-preferences/
PATCH /notification-preferences/

GET|POST         /reminders/
GET|PATCH|DELETE /reminders/{id}/
```

Les routes de rappels **s'ajoutent à cette spec** : la spec 03 §11 donne le
modèle et la spec 01 §24 le comportement, mais aucune ne prévoyait de moyen de
les régler.

`GET /notifications/` porte son compteur `unread` à côté de la page : un entier
ne mérite pas sa propre requête, et l'interface en a besoin pour sa pastille.
`reminder` et `scheduled_on` n'en sortent pas — ce sont les rouages de
l'idempotence, pas une information pour le lecteur.

`GET /notification-preferences/` rend **les six types**, défauts compris, même
sans aucune ligne en base. Une préférence absente n'est pas une préférence : si
chaque appelant décidait du défaut, la réponse dépendrait de qui pose la
question. `PATCH` accepte une liste partielle sous `results`.

Les rappels ne partent **pas par email** par défaut : un « pense à journaliser
ton déjeuner » quotidien devient du bruit qu'on filtre, et une boîte filtrée ne
rappelle plus rien. Les événements sociaux, rares, y ont droit.

`push_enabled` est rendu mais toujours faux : la colonne existe (spec 03 §11),
aucun canal ne la lit encore, et l'interface affiche la case désactivée plutôt
qu'une case sans effet.

`POST /reminders/` sur un type déjà réglé **met à jour** plutôt que d'échouer
sur la contrainte d'unicité : « un seul rappel par type » se règle, il ne se
refuse pas. `days_of_week` porte des entiers de 0 (lundi) à 6, convention
Python comme les surcharges d'objectifs ; une liste vide est refusée — un
rappel qui ne part jamais se désactive, il ne se vide pas.

Un rappel dû ne produit **qu'une notification par journée**, garantie par une
contrainte d'unicité sur `(reminder, scheduled_on)` plutôt que par un verrou de
cache : la notification est la preuve qu'il est parti. Au-delà d'une fenêtre de
rattrapage d'une heure, un rappel manqué est **sauté et journalisé** — « pense à
te peser ce matin » à midi n'est plus un rappel.

`GET /dashboard/` porte désormais `unread_notifications` (spec 04 §16).

## 20. Account

```text
POST   /account/change-password/
DELETE /account/
```

Suppression :

```json
{
  "username_confirmation": "teo"
}
```

Suppression immédiate après confirmation exacte.
