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
```

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

DELETE d'un type système = désactivation.

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

La génération async retourne un `task_id`.

## 9. Async tasks

```text
GET /tasks/{id}/
```

Réponse type :

```json
{
  "status": "pending",
  "progress": 20,
  "result": null,
  "error": null
}
```

Statuts :

- pending
- processing
- success
- failed

## 10. IA

```text
POST /ai/meal-scan/
POST /ai/voice-log/
```

Les endpoints IA créent une tâche et retournent des suggestions.

Ils ne créent pas directement des entrées de journal.

Le frontend confirme ensuite via `/diary/entries/`.

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

- `meal_plan_id`
- `recipe_ids[]`
- `dates[]`

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

Pour `app_users`, une visibilité globale suffit.

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

`charts` calcule la moyenne mobile côté backend.

## 15. Progress photos

```text
GET    /progress/photos/
POST   /progress/photos/
GET    /progress/photos/{id}/
PATCH  /progress/photos/{id}/
DELETE /progress/photos/{id}/
```

Le fichier n'est pas modifié : supprimer/réuploader pour remplacer.
Les métadonnées peuvent être patchées.

## 16. Dashboard

```text
GET /dashboard/?date=YYYY-MM-DD
```

Réponse agrégée :

- objectifs ;
- calories consommées/restantes ;
- macros ;
- repas ;
- poids récent ;
- progression ;
- config widgets ;
- notifications importantes.

## 17. Reports

```text
GET  /reports/summary/?from=...&to=...
POST /reports/pdf/
POST /reports/csv/
```

PDF async si nécessaire.
CSV synchrone si suffisamment léger.

## 18. Analysis

```text
GET /analysis/food/?from=...&to=...&nutrient=protein
GET /analysis/weekly/?from=...
```

## 19. Notifications

```text
GET  /notifications/
POST /notifications/{id}/read/
POST /notifications/read-all/

GET   /notification-preferences/
PATCH /notification-preferences/
```

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
