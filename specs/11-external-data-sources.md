# 11 — Sources de données alimentaires

## 1. Stratégie

Sources :

1. **Ciqual** : aliments génériques français (version 2020, seule diffusée publiquement à ce jour).
2. **Open Food Facts** : produits emballés / marques / code-barres.
3. **Aliments utilisateur** : base interne.
4. **USDA FoodData Central** : fallback facultatif ultérieur.

## 2. Ciqual

### Ce que contient réellement le jeu

| Fichier | Contenu | Volume |
| --- | --- | --- |
| `alim_*.xml` | aliments | 3 185 |
| `const_*.xml` | constituants | 67 |
| `compo_*.xml` | composition | 211 898 lignes, 55 Mo |
| `alim_grp_*.xml` | groupes | 136 |

Deux pièges vérifiés à l'implémentation :

1. l'encodage est **`windows-1252`** et les décimales utilisent la **virgule** ;
2. les fichiers **ne sont pas du XML bien formé** : le texte contient des `<`
   bruts, dans les noms (`Panaché préemballé (<1° alc.)`) et dans les milliers
   de teneurs de la forme `< 0,01`. Ils doivent être échappés avant analyse.

### Interprétation des teneurs

| Valeur | Signification | Stockage |
| --- | --- | --- |
| `-` | non mesurée | `NULL` |
| `traces` | mesurée, négligeable | `0` |
| `< 0,01` | mesurée sous le seuil de détection | `0` |
| `59,7` | valeur | `Decimal` |

Un tiret n'est pas un zéro : c'est la règle de la spec 01 §8.

### Vitamine A

Ciqual ne publie pas de vitamine A : elle se reconstitue à partir du rétinol
et du bêta-carotène, selon la convention européenne.

```text
vitamine A (µg RE) = rétinol + bêta-carotène / 6
```

Approche :

- télécharger le jeu officiel ;
- l'importer localement dans PostgreSQL ;
- ne pas dépendre d'une API live pour la recherche ;
- créer une commande Django `import_ciqual`;
- gérer versions et upserts ;
- ne pas permettre aux utilisateurs de modifier ces fiches ;
- permettre à l'admin de désactiver une fiche.

Attribution à conserver dans l'application/documentation :

`Anses. 2020. Table de composition nutritionnelle des aliments Ciqual`

Les données sont réutilisables selon les conditions de la Licence Ouverte et la source/version doivent être indiquées.

## 3. Open Food Facts

### Ce que l'API impose réellement

Vérifié par sondage direct de l'API au moment de l'intégration.

**Les quotas sont par adresse IP, pas par utilisateur :**

| Usage | Quota annoncé |
| --- | --- |
| Lecture d'un produit | 15 req/min/IP |
| Recherche texte | 10 req/min/IP |

Le backend ne présente qu'une adresse pour tous les comptes : le quota est
donc **commun**. Deux étages de limitation sont nécessaires — le throttling DRF
par utilisateur (`off_barcode`, `off_search`) et un budget global partagé dans
Redis (`common.rate_limit`). Le second est le seul à protéger d'un dépassement
collectif ; quand il est épuisé, aucune requête ne part.

**Deux services distincts sont interrogés :**

```text
lecture produit   GET https://world.openfoodfacts.org/api/v3/product/{code}.json
recherche texte   GET https://search.openfoodfacts.org/search
```

L'endpoint historique `/api/v2/search` renvoie une page **HTML** « Page
temporarily unavailable » : la recherche passe par Search-a-licious.

Les deux n'ont pas la même forme — `brands` est une chaîne `"Nutella, Ferrero"`
côté produit, un tableau côté recherche. D'où la règle retenue : **la recherche
ne sert qu'à découvrir** (code, nom, marque) et l'endpoint produit fait seul
autorité pour la nutrition et la mise en cache. Une seule conversion à écrire
et à maintenir.

**Le client doit survivre à une réponse non-JSON.** C'est le mode de panne réel
de cette API : une page HTML servie avec un statut 200. Un `response.json()`
naïf lèverait une exception en pleine requête utilisateur.

**Produit inconnu :** HTTP 404 avec `result.id = "product_not_found"`. C'est un
cas nominal, distinct d'une panne, et il mène à la création manuelle.

### Conversion des nutriments

Trois pièges, tous silencieux :

1. `energy_100g` est en **kilojoules**, `energy-kcal_100g` en kilocalories.
   Pour le Nutella, 2252 contre 539 : se tromper multiplie les calories par 4,18.
2. Les micronutriments sont exprimés **en grammes** (`calcium_100g = 0.148`
   avec `calcium_unit = "g"`), quand le modèle stocke des mg et des µg.
3. `nutrition_data_per` peut valoir `serving`. Seules les clés `_100g` sont
   lues ; en leur absence la valeur reste `NULL`.

| Champs | Clé | Conversion |
| --- | --- | --- |
| `energy_kcal` | `energy-kcal_100g` | tel quel |
| macronutriments, fibres, sucres, sel | `<nutriment>_100g` | tel quel (g) |
| sodium, cholestérol, potassium, calcium, fer, magnésium, B6, C, E | `<nutriment>_100g` | × 1 000 |
| vitamines A, B12, D, K | `<nutriment>_100g` | × 1 000 000 |

Les valeurs sont bornées avant écriture. La base est collaborative et contient
des saisies aberrantes ; les champs étant en `max_digits=9, decimal_places=3`,
une valeur fantaisiste ferait échouer la requête au niveau de la base. Une
valeur hors domaine reste `NULL` plutôt que d'être tronquée.

### Codes-barres

Les standards du commerce s'arrêtent à 14 chiffres, mais Open Food Facts
référence aussi des codes plus longs — on en rencontre de 18 chiffres dans ses
résultats. La validation accepte donc 8 à 24 chiffres ; les candidats hors de
cette règle sont écartés des résultats de recherche, faute de pouvoir être
ouverts.

### Architecture

```text
requête utilisateur
→ recherche locale immédiate (Ciqual, aliments personnels, cache OFF)
→ recherche OFF uniquement sur demande explicite
→ normalisation
→ affichage
→ mise en cache PostgreSQL du produit réellement choisi
```

Important :

- ne pas faire de search-as-you-type sur OFF ;
- User-Agent identifié `NomApp/Version (contact)`, exigé par la source ;
- gérer 429/503, timeout et réponse non-JSON ;
- continuer à fonctionner sur les données locales si OFF est indisponible ;
- rafraîchir les fiches de plus de 30 jours, en tâche Celery, sans faire
  attendre l'utilisateur ;
- `OFF_ENABLED=False` coupe la source sans redéploiement.

Qualité :

- données collaboratives potentiellement incomplètes ;
- valeurs manquantes `null` ;
- fiches jamais marquées « vérifiées » ;
- source visible ;
- utilisateur peut créer une copie personnelle, pas corriger le cache global.

Les valeurs sont enregistrées pour 100 g, comme les normalise la source.
Aucune conversion ml ↔ g n'est tentée sans densité connue (spec 01 §9) : c'est
une approximation assumée pour les boissons.

### Point de vigilance licence

Open Food Facts est sous ODbL avec obligations d'attribution/share-alike selon
le type de réutilisation.

Comme le projet est initialement privé, documenter malgré tout la provenance.

Avant toute diffusion publique ou commerciale, effectuer une revue spécifique
de la licence et de la manière dont la base OFF est combinée avec les autres
sources.

## 4. Barcode

Ordre de résolution :

1. aliment personnel de l'utilisateur portant ce code ;
2. cache local des produits déjà rapatriés ;
3. endpoint produit d'Open Food Facts ;
4. sinon 404, menant à la création manuelle avec le code prérempli.

## 5. Recherche

Ciqual et cache local :

- PostgreSQL ;
- accents ;
- trigrammes ;
- classement ;
- résultats instantanés.

OFF :

- appel séparé et throttlé ;
- pas chaque frappe.

### Langues interrogées

Open Food Facts indexe le nom des produits **par langue**. Restreindre la
recherche au français rend donc invisibles les produits nommés ailleurs, alors
même que le scan de code-barres, lui, n'a jamais eu cette restriction : on
trouve un produit suédois en scannant son emballage, mais pas en tapant son nom.

Les langues sont un **réglage par compte** — `UserSettings.food_search_languages`,
`fr` et `en` par défaut, cinq au maximum, prises dans un catalogue que le serveur
expose avec les réglages. On ne fait pas ses courses toujours dans le même pays.

Mesuré sur l'API réelle, l'ajout du suédois double environ le nombre de
résultats : `filmjölk` passe de 24 à 45, `knäckebröd` de 20 à 55.

### Ce que le réglage ne corrige pas

La **couverture** d'Open Food Facts varie fortement selon les pays. ICA, premier
distributeur suédois, y compte environ 1 500 produits, quand chaque enseigne
française en dépasse 10 000. Un produit absent de la source reste absent quelle
que soit la langue interrogée : la réponse est la création manuelle, que la
lecture d'étiquette doit rendre rapide.

## 6. USDA FoodData Central

Fallback facultatif.

Ne pas l'intégrer dans la V1 tant que Ciqual + OFF couvrent le besoin.

Si activé :

- clé API ;
- abstraction provider ;
- respecter rate limits ;
- normaliser les nutriments ;
- source visible.

## 7. Sources officielles

Ciqual :

- https://ciqual.anses.fr/

Open Food Facts :

- https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/
- https://support.openfoodfacts.org/help/en-gb/12-api-data-reuse/94-are-there-conditions-to-use-the-api

USDA FoodData Central :

- https://fdc.nal.usda.gov/api-guide/
