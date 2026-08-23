# 08 — Tests et qualité

## 1. Philosophie

Pas de pourcentage de couverture arbitraire.

Règle :

> Toute règle métier importante doit avoir un test.

## 2. Backend

Outils :

- pytest
- pytest-django

Tester :

### Accounts

- username case-insensitive ;
- demandes ;
- acceptation/refus ;
- suspension ;
- reset ;
- suppression compte.

### Nutrition

- calcul objectifs ;
- overrides jours ;
- priorité calories ;
- glucides nets ;
- Decimal.

### Foods

- permissions ;
- portions ;
- source ;
- cache OFF ;
- données inconnues null ;
- recherche trigramme.

### Diary

- snapshot ;
- copie journée ;
- duplication ;
- bulk dates ;
- move meal ;
- suppression source sans impact historique.

### Recipes

- calcul par portion ;
- cache ;
- modification non rétroactive.

### Social

- amitié ;
- partage ;
- révocation ;
- impossibilité de modifier une ressource reçue.

### Progress

- une mesure poids/date ;
- moyenne mobile ;
- photos privées.

### AI

- validation JSON ;
- résultat invalide ;
- retries planner ;
- absence provider ;
- aucune écriture journal automatique.

## 3. Permissions

Tests explicites IDOR :

- User A ne peut pas lire/modifier User B ;
- sauf partage prévu ;
- un partage lecture ne donne pas écriture ;
- suspension invalide l'accès.

## 4. Frontend

Outils :

- Vitest
- React Testing Library

Tester :

- formulaires critiques ;
- calculs d'affichage ;
- erreurs ;
- confirmation IA ;
- édition journal ;
- dashboard ;
- permissions UI.

## 5. E2E

Playwright :

1. demande inscription ;
2. acceptation admin simulée/fixture ;
3. login ;
4. onboarding ;
5. ajout aliment ;
6. édition journal ;
7. recette ;
8. planner ;
9. partage ;
10. suppression ami/révocation ;
11. progression ;
12. suppression compte.

Scanner et IA peuvent être mockés.

## 6. CI

À chaque push pertinent :

Backend :

- lint ;
- tests.

Frontend :

- lint ;
- typecheck ;
- tests ;
- build.

Production main :

- tous les checks obligatoires ;
- Railway Wait for CI activé.

## 7. Outils qualité

Python :

- Ruff pour lint/format.

Frontend :

- ESLint ;
- Prettier ;
- `tsc --noEmit`.

## 8. Definition of Done

Une feature est terminée si :

- comportement conforme ;
- tests ;
- sécurité ;
- erreurs ;
- migrations ;
- docs ;
- pas de secret ;
- UI loading/error/empty pertinente ;
- CI verte.
