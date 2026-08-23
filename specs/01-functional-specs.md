# 01 — Spécifications fonctionnelles

## 1. Comptes

### Demande d'inscription

Champs :

- prénom ;
- nom ;
- nom d'utilisateur unique ;
- mot de passe ;
- confirmation du mot de passe ;
- email facultatif.

Le nom d'utilisateur :

- est obligatoire ;
- sert à la connexion ;
- sert à la recherche sociale ;
- est unique de manière insensible à la casse ;
- reste modifiable en conservant cette unicité.

L'email :

- est facultatif ;
- ne sert jamais à la recherche sociale ;
- peut servir aux notifications de compte ;
- permet le mot de passe oublié.

### Validation

Une demande crée un `RegistrationRequest`.

L'administrateur peut :

- accepter ;
- refuser.

Acceptation :

- création du compte actif ;
- email d'acceptation seulement si email renseigné et notification autorisée ;
- notification interne si applicable.

Refus :

- email de refus si email renseigné et notification autorisée ;
- suppression de la demande après traitement ;
- nouvelle demande ultérieure autorisée.

Un compte non actif ne peut pas utiliser l'application.

### Mot de passe

- reset par email si email renseigné ;
- sinon contact admin ;
- admin peut forcer une réinitialisation ;
- admin ne connaît jamais le mot de passe actuel.

## 2. Onboarding

Étapes :

1. informations personnelles ;
2. objectif ;
3. niveau d'activité ;
4. rythme de perte/prise de poids ;
5. calcul calories ;
6. proposition macros ;
7. résumé.

Données :

- date de naissance ;
- sexe utilisé pour le calcul ;
- taille ;
- poids ;
- niveau d'activité ;
- objectif ;
- poids cible ;
- rythme.

Objectifs :

- perte ;
- maintien ;
- prise.

Niveau d'activité :

- sédentaire ;
- légèrement actif ;
- modérément actif ;
- très actif ;
- extrêmement actif.

Le niveau d'activité sert uniquement au calcul initial. Pas de gestion d'exercice dans la V1.

L'utilisateur peut remplacer manuellement les calories et macros proposées.

Application réservée aux adultes 18+.

## 3. Calcul calorique

Le calcul :

- utilise une formule métabolique standard déterministe ;
- applique un coefficient d'activité ;
- applique le déficit/surplus correspondant au rythme choisi ;
- n'utilise jamais l'IA.

Si la valeur semble potentiellement déraisonnable :

- afficher un avertissement ;
- ne pas bloquer la saisie manuelle.

Texte attendu :

> Il s'agit d'une estimation et non d'une recommandation médicale.

## 4. Objectifs nutritionnels

Valeurs :

- calories ;
- protéines ;
- glucides ;
- lipides ;
- fibres et micronutriments configurables.

Macros :

- mode pourcentage OU grammes ;
- les deux représentations peuvent être calculées pour affichage ;
- les calories sont prioritaires en cas d'incohérence.

Objectifs :

- même objectif par défaut chaque jour ;
- surcharge possible selon le jour de la semaine ;
- surcharge calories + macros ;
- objectifs par repas pour calories et macros ;
- historique des objectifs conservé ;
- changement d'objectif non rétroactif.

Glucides nets :

`glucides - fibres`

Micronutriments suivis au minimum :

- fibres ;
- sucres ;
- sodium ;
- sel ;
- cholestérol ;
- potassium ;
- calcium ;
- fer ;
- magnésium ;
- vitamine A ;
- vitamine B6 ;
- vitamine B12 ;
- vitamine C ;
- vitamine D ;
- vitamine E ;
- vitamine K.

## 5. Journal alimentaire

Repas par défaut :

- Petit-déjeuner ;
- Déjeuner ;
- Dîner ;
- Collations.

L'utilisateur peut :

- renommer ;
- créer ;
- désactiver ;
- réordonner ;
- déplacer les aliments entre repas par drag & drop.

Chaque entrée peut être :

- modifiée ;
- supprimée ;
- dupliquée ;
- déplacée.

Quantités :

- décimales autorisées ;
- g ;
- kg ;
- ml ;
- cl ;
- portion ;
- unité ;
- cuillère à café ;
- cuillère à soupe ;
- portions personnalisées.

Les données nutritionnelles se recalculent instantanément à l'écran lors d'un changement de quantité.

Horodatage :

- automatique à l'ajout ;
- modifiable manuellement.

Journal modifiable :

- passé ;
- aujourd'hui ;
- futur.

Copie :

- repas vers date ;
- journée vers date ;
- journée vers plusieurs dates ;
- horaires copiés ;
- ajout d'un même aliment sur plusieurs dates choisies librement.

Une copie/duplication normale repart de la version actuelle de l'aliment. Les entrées historiques déjà existantes restent basées sur leur snapshot.

## 6. Snapshots

Lorsqu'un aliment ou une recette est ajouté au journal, stocker un snapshot des informations nécessaires :

- nom ;
- marque ;
- source ;
- quantité ;
- unité ;
- calories ;
- macros ;
- micronutriments.

Une modification ou suppression future de la source ne modifie jamais l'historique.

## 7. Recherche alimentaire

Sources principales :

1. favoris / récents / fréquents ;
2. aliments personnels ;
3. Ciqual ;
4. produits de marque Open Food Facts.

Recherche :

- à partir de 2 caractères ;
- insensible à la casse ;
- insensible aux accents ;
- tolérante aux petites fautes ;
- PostgreSQL `pg_trgm` recommandé ;
- pas d'IA pour une recherche normale.

Récents :

- 50 derniers aliments distincts.

Fréquents :

- calculés à partir de `use_count`.

Favoris :

- étoile manuelle.

Classement privilégié :

1. favoris ;
2. récents ;
3. fréquents ;
4. correspondance exacte ;
5. correspondance similaire ;
6. pondération de source.

## 8. Qualité nutritionnelle

Valeur inconnue :

- `null` / `—` à l'écran ;
- jamais `0` si inconnue.

Un produit partiellement renseigné reste utilisable.

Un utilisateur ne modifie pas directement une fiche CIQUAL/OFF ; il peut créer sa propre version.

Afficher la source de l'aliment.

## 9. Portions

Une portion appartient à un seul aliment.

Exemples :

- 1 tranche = 32 g ;
- 1 pot = 125 g ;
- 1 cuillère = 15 g.

Plusieurs portions par aliment.

Les portions locales ajoutées sur un aliment global sont privées à leur créateur.

Ne jamais convertir automatiquement ml ↔ g sans densité connue.

## 10. Code-barres

Mobile :

`Ajouter → Scanner → caméra`

Produit trouvé :

`fiche → quantité → repas → ajout`

Produit inconnu :

`créer produit → barcode prérempli`

Saisie manuelle du code-barres disponible.

Les produits inconnus créés restent dans MyFitnessPalworld et ne sont pas envoyés automatiquement à Open Food Facts.

## 11. Aliments personnalisés

- privés par défaut ;
- partageables ;
- peuvent avoir plusieurs portions ;
- peuvent être dupliqués ;
- peuvent être utilisés dans recettes et repas.

## 12. Ajout rapide

Une `DiaryEntry` de type `quick_add`.

Peut contenir :

- calories seules ;
- calories + protéines + glucides + lipides ;
- note facultative.

## 13. Repas enregistrés

Un repas enregistré = ensemble réutilisable d'aliments et/ou recettes déjà portionnés.

Fonctions :

- créer ;
- modifier ;
- supprimer ;
- dupliquer ;
- rechercher ;
- partager ;
- ajouter au journal.

L'ajout au journal crée des entrées normales indépendantes et snapshotées.

## 14. Recettes

Une recette = ingrédients préparés ensemble puis divisés en portions.

Champs :

- nom ;
- description ;
- instructions texte libre ;
- nombre de portions ;
- ingrédients ;
- visibilité ;
- favori.

Fonctions :

- calcul nutritionnel ;
- cache recalculé à chaque modification ;
- dupliquer ;
- partager ;
- ajouter N portions au journal.

Modifier une recette ne modifie jamais les anciennes entrées du journal.

## 15. Meal Planner

Génération :

- 1 jour ;
- plusieurs jours ;
- semaine.

Contraintes :

- calories ;
- protéines ;
- glucides ;
- lipides ;
- nombre de repas ;
- allergies ;
- aliments aimés ;
- aliments détestés.

Pas de contrainte :

- budget ;
- temps de préparation ;
- régime alimentaire.

Sources possibles :

- recettes personnelles ;
- aliments fréquents ;
- nouvelles recettes proposées par IA.

Une recette IA peut être enregistrée après validation.

Tolérance :

- calories ±5 % ;
- protéines ±10 % ;
- glucides ±10 % ;
- lipides ±10 %.

Le backend peut demander jusqu'à 3 générations/corrections.

L'utilisateur peut :

- régénérer un seul repas ;
- modifier le plan ;
- ajouter tout le plan au journal.

L'ajout :

- n'écrase jamais les données existantes ;
- demande confirmation si un repas contient déjà des entrées.

## 16. Liste de courses

Génération depuis :

- planning ;
- journées ;
- recettes.

Regrouper les ingrédients compatibles :

`150 g poulet + 300 g poulet = 450 g poulet`

Fonctions :

- ajouter manuellement ;
- supprimer ;
- modifier quantité ;
- cocher acheté ;
- partager.

Pas d'historique automatique après suppression.

Partage visible uniquement par comptes actifs.

## 17. Social

Ajout d'amis :

- recherche partielle par username ;
- demande ;
- acceptation/refus ;
- suppression.

Pas de blocage utilisateur dans la V1.

Amitié bidirectionnelle.

Retirer un ami révoque automatiquement les partages spécifiques destinés à cet ami.

## 18. Partage

Types :

- privé ;
- utilisateurs spécifiques ;
- tous les utilisateurs actifs.

Aucun partage public sans compte.

Ressources partageables :

- aliment personnel ;
- recette ;
- repas enregistré ;
- journal ;
- progression ;
- liste de courses.

Une ressource copiée devient une copie indépendante.

Le journal partagé est lecture seule.

Le partage journal et le partage progression sont distincts.

Les photos de progression ne sont jamais partageables.

## 19. Poids et mensurations

Taille :

- profil ;
- obligatoire à l'onboarding.

Poids :

- 1 entrée par date ;
- nouvelle saisie pour la même date = modification.

Mensurations facultatives :

- taille ;
- hanches ;
- poitrine ;
- bras ;
- cuisse ;
- masse grasse.

Graphique poids :

- poids réel ;
- moyenne mobile 7 jours ;
- objectif ;
- tendance.

## 20. Photos de progression

Plusieurs photos par date :

- face ;
- profil ;
- dos ;
- autre.

Métadonnées :

- date ;
- snapshot poids facultatif ;
- note.

Règles :

- compression automatique ;
- bucket privé ;
- URL signée temporaire ;
- suppression définitive ;
- jamais partagées.

## 21. Food Analysis

Analyse par nutriment :

- calories ;
- protéines ;
- glucides ;
- lipides ;
- fibres ;
- sucres ;
- sodium ;
- micronutriments.

Périodes :

- jour ;
- semaine ;
- mois ;
- intervalle personnalisé.

Afficher :

- principales sources ;
- quantité apportée ;
- pourcentage de contribution.

## 22. Rapports

Exports :

- CSV ;
- PDF.

Période :

- intervalle personnalisé.

Graphiques :

- poids ;
- calories ;
- protéines ;
- glucides ;
- lipides ;
- fibres ;
- micronutriments.

Résumé hebdomadaire :

- moyennes ;
- respect des objectifs ;
- variation du poids ;
- top aliments.

## 23. Dashboard

Widgets possibles :

- calories consommées/restantes ;
- macros ;
- repas du jour ;
- poids ;
- courbe du poids ;
- fibres ;
- micronutriments ;
- progression objectif ;
- raccourcis d'ajout.

Pas de widget eau.

Personnalisation :

- afficher/masquer ;
- drag & drop ;
- persistance serveur.

## 24. Notifications

Canaux :

- interne ;
- push PWA ;
- email si email renseigné.

Préférences indépendantes par type d'événement.

Rappels :

- repas ;
- pesée ;
- éléments planifiés.

Jours de semaine configurables.

Un seul rappel par type.

## 25. Offline

Mode simple.

Sans connexion :

- assets/app shell peuvent s'afficher ;
- informer clairement que la connexion est nécessaire pour modifier les données ;
- pas de synchronisation offline complexe.
