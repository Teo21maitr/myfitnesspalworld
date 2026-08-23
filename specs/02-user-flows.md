# 02 — Parcours utilisateurs

## 1. Inscription

1. Ouvrir « Demander un compte ».
2. Saisir prénom, nom, username, mot de passe, email facultatif.
3. Validation frontend + backend.
4. Création `RegistrationRequest`.
5. Afficher « Votre demande est en attente ».
6. Admin accepte/refuse.
7. Si accepté : création compte actif.
8. Si email présent : envoyer notification selon préférence / règles transactionnelles.
9. Utilisateur se connecte.
10. Onboarding obligatoire si non terminé.

## 2. Ajout alimentaire classique

1. Depuis n'importe quel écran mobile : bouton `+`.
2. Choisir « Ajouter un aliment ».
3. Choisir le repas et la date si nécessaire.
4. Taper au moins 2 caractères.
5. Afficher favoris/récents/fréquents et résultats.
6. Choisir un aliment.
7. Choisir quantité/unité/portion.
8. Modifier l'heure si besoin.
9. Valider.
10. Backend crée `DiaryEntry` avec snapshot.
11. Dashboard et journal sont rafraîchis.

## 3. Scanner code-barres

1. `+` → Scanner.
2. Autorisation caméra.
3. Scanner le barcode.
4. Chercher cache local puis Open Food Facts.
5. Si trouvé : afficher produit.
6. Si inconnu : proposer création manuelle avec barcode prérempli.
7. Choisir quantité et repas.
8. Ajouter au journal.

## 4. Meal Scan

1. `+` → Meal Scan.
2. Prendre une ou plusieurs photos.
3. Upload temporaire.
4. Création tâche async.
5. Analyse IA : aliments probables + quantités probables.
6. Recherche de correspondances dans la base.
7. Afficher :
   - suggestion ;
   - quantité estimée ;
   - niveau de confiance si disponible ;
   - avertissement « Estimation IA — vérifiez les quantités ».
8. L'utilisateur peut :
   - changer l'aliment ;
   - changer la quantité ;
   - supprimer ;
   - ajouter un oubli.
9. Validation.
10. Frontend appelle les endpoints normaux du journal.
11. Photos Meal Scan supprimées immédiatement après traitement.

## 5. Voice Logging

1. `+` → Voix.
2. Enregistrer en français.
3. Upload temporaire.
4. Speech-to-text.
5. Parser IA du texte.
6. Afficher aliments/quantités détectés.
7. Correction utilisateur.
8. Confirmation.
9. Ajout via API journal normale.
10. Audio supprimé immédiatement après transcription/traitement.

## 6. Création recette

1. Recettes → Nouvelle recette.
2. Saisir nom, description, instructions, portions.
3. Ajouter ingrédients via recherche.
4. Backend calcule les valeurs totales et par portion.
5. Enregistrer.
6. Option favori/partage.
7. Plus tard : Ajouter au journal → date + repas + portions.

## 7. Meal Planner

1. Planner → Générer.
2. Choisir 1 jour / plusieurs / semaine.
3. Définir ou reprendre objectifs nutritionnels.
4. Définir nombre de repas.
5. Allergies, goûts positifs/négatifs.
6. Lancer génération.
7. Afficher état tâche async.
8. Backend valide nutrition calculée depuis la BDD.
9. Jusqu'à 3 corrections IA si hors tolérance.
10. Afficher plan.
11. Utilisateur peut éditer ou régénérer un repas.
12. « Ajouter au journal ».
13. Si conflit avec repas existant : confirmer.
14. Copier sous forme d'entrées indépendantes.

## 8. Partage recette

1. Ouvrir recette.
2. Partager.
3. Choisir :
   - privé ;
   - utilisateur(s) ;
   - tous les utilisateurs actifs.
4. Destinataire ouvre la recette en lecture.
5. Bouton « Copier dans mes recettes ».
6. Nouvelle copie indépendante appartenant au destinataire.

## 9. Partage journal

1. Paramètres confidentialité / journal.
2. Choisir visibilité.
3. Si utilisateurs spécifiques : sélectionner comptes.
4. Destinataire consulte journal en lecture seule.
5. Aucune modification distante possible.
6. Progression non incluse sauf partage progression séparé.
7. Photos jamais incluses.

## 10. Poids

1. Progression → Ajouter poids.
2. Date + kg + note facultative.
3. Si date existe : mettre à jour.
4. Graphique :
   - mesure ;
   - moyenne mobile 7 jours ;
   - tendance ;
   - objectif.

## 11. Suppression de compte

1. Paramètres → Supprimer mon compte.
2. Explications de suppression définitive.
3. Demander username exact.
4. Revalidation backend.
5. Suppression définitive de toutes les données détenues et fichiers privés.
6. Révocation sessions/tokens.
