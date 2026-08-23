# 06 — Frontend et UX

## 1. Principes

- mobile-first ;
- responsive ;
- mêmes fonctionnalités desktop/mobile ;
- interactions quotidiennes rapides ;
- une main sur mobile autant que possible ;
- interface intermédiaire : ni ultra-minimaliste ni surchargée ;
- santé / nutrition moderne.

## 2. Navigation mobile

Bottom bar :

1. Accueil
2. Journal
3. `+`
4. Progression
5. Profil

Menu `+` :

- Ajouter aliment
- Scanner
- Meal Scan
- Voix
- Ajout rapide

Recettes / Planner / Courses : accessibles depuis accueil ou menu secondaire.

## 3. Navigation desktop

Sidebar :

- Accueil
- Journal
- Aliments
- Recettes
- Planner
- Courses
- Progression
- Amis
- Paramètres

## 4. Pages

### Auth

- Connexion
- Demande d'inscription
- Compte en attente
- Mot de passe oublié
- Reset mot de passe

### Onboarding

- Profil
- Objectif
- Activité
- Rythme
- Calories
- Macros
- Résumé

### Principal

- Accueil
- Journal
- Recherche aliments
- Fiche aliment
- Scanner
- Meal Scan
- Voice Logging
- Mes aliments
- Mes repas
- Recettes
- Fiche recette
- Planner
- Liste de courses
- Progression
- Photos
- Rapports
- Food Analysis
- Amis
- Partages
- Profil
- Objectifs
- Notifications
- Confidentialité
- Paramètres

## 5. Dashboard

Exemple :

```text
Calories
1850 / 2300 kcal

Protéines
135 / 160 g

Glucides
210 / 280 g

Lipides
55 / 75 g

Poids
78,2 kg
-2,4 kg depuis le début
```

Widgets drag & drop et masquables.

## 6. Journal mobile

Carte par repas.

Chaque repas affiche :

- nom ;
- calories ;
- objectif ;
- macros facultatives ;
- aliments.

Actions aliment :

- tap : fiche ;
- menu : modifier / dupliquer / supprimer / déplacer ;
- drag & drop entre repas ;
- swipe facultatif :
  - gauche supprimer ;
  - droite dupliquer.

Les gestes ne doivent jamais être l'unique moyen d'effectuer une action.

## 7. Recherche

Après 2 caractères.

Chaque ligne :

- nom ;
- marque ;
- calories / 100 g ou portion ;
- source ;
- favori.

Afficher source discrètement.

## 8. Thèmes

Modes :

- light ;
- dark ;
- system.

Light :

- fond blanc ;
- bleu principal ;
- cartes claires.

Dark :

- bleu nuit / gris très sombre ;
- contraste AA minimum visé ;
- couleurs de graphiques lisibles.

## 9. Branding

Logo :

- silhouette homme chauve ;
- simple ;
- sérieuse ;
- évoque un diététicien ;
- pas de caricature ;
- pas de corps ultra-musclé.

Texte : `MyFitnessPalworld`.

## 10. PWA

- manifest ;
- icônes ;
- installable ;
- service worker ;
- cache assets ;
- app shell offline ;
- push notifications.

Offline :

- indiquer clairement absence de connexion ;
- lecture du contenu déjà rendu/cache possible ;
- pas d'écriture métier offline.

## 11. États UI obligatoires

Toute page de données doit prévoir :

- loading ;
- skeleton si utile ;
- erreur ;
- vide ;
- succès ;
- offline ;
- permission refusée ;
- contenu supprimé/inaccessible.

## 12. Accessibilité

Minimum :

- labels de formulaire ;
- navigation clavier desktop ;
- focus visible ;
- boutons suffisamment grands sur mobile ;
- contrastes lisibles ;
- alternatives textuelles aux icônes importantes.
