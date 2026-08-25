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

Utiliser l'API actuelle recommandée au moment de l'intégration.

Architecture :

```text
query utilisateur
→ recherche locale immédiate
→ éventuellement OFF
→ normalisation
→ affichage
→ cache PostgreSQL si réellement utilisé
```

Important :

- ne pas faire de search-as-you-type agressif directement sur OFF ;
- respecter les rate limits ;
- utiliser un User-Agent identifié ;
- gérer 429/503 ;
- continuer à fonctionner avec les données locales si OFF est indisponible ;
- rafraîchir les produits cachés anciens, valeur cible 30 jours.

Qualité :

- données collaboratives potentiellement incomplètes ;
- valeurs manquantes = null ;
- source visible ;
- utilisateur peut créer une copie personnelle, pas corriger directement le cache global.

### Point de vigilance licence

Open Food Facts est sous ODbL avec obligations d'attribution/share-alike selon le type de réutilisation.

Comme le projet est initialement privé, documenter malgré tout la provenance.

Avant toute diffusion publique ou commerciale, effectuer une revue spécifique de la licence et de la manière dont la base OFF est combinée avec les autres sources.

## 4. Barcode

Ordre recommandé :

1. cache local ;
2. OFF product endpoint ;
3. si absent : création manuelle.

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
