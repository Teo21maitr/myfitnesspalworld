# 00 — Vue d'ensemble

## 1. Produit

**Nom : MyFitnessPalworld**

Application web PWA de suivi alimentaire et nutritionnel inspirée fonctionnellement de MyFitnessPal, y compris des fonctionnalités habituellement premium.

Usage prévu : **privé**, pour l'utilisateur principal et ses proches. L'application n'est pas pensée comme un SaaS public à grande échelle dans sa première version.

> Si le produit devient public, le nom « MyFitnessPalworld » devra être réévalué en raison de sa proximité avec une marque existante.

## 2. Objectif

Permettre à l'utilisateur de :

- calculer un objectif calorique ;
- suivre calories, macronutriments et micronutriments ;
- enregistrer rapidement ses repas ;
- utiliser aliments génériques, produits de marque et aliments personnalisés ;
- suivre son poids et ses mensurations ;
- créer recettes et repas enregistrés ;
- générer un planning de repas ;
- produire automatiquement une liste de courses ;
- partager certaines données avec d'autres comptes actifs ;
- utiliser l'IA pour accélérer la saisie sans en faire une source nutritionnelle de vérité.

## 3. Stack

### Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Tailwind CSS
- shadcn/ui
- React Hook Form
- Zod
- PWA

### Backend

- Django
- Django REST Framework
- PostgreSQL
- Celery
- Redis
- Gunicorn

### Déploiement

- GitHub
- Railway
- PostgreSQL Railway
- Redis Railway
- stockage objet S3-compatible
- GitHub Actions
- branche `main` déployée en production

## 4. Environnements

Deux environnements applicatifs seulement :

1. `local`
2. `production`

Il n'y a pas d'environnement Railway de staging obligatoire.

Branches :

- `develop` : développement local ;
- `main` : production.

Le push direct sur `main` est autorisé.

Railway doit attendre les checks GitHub Actions avant de déployer `main`.

## 5. Architecture monorepo

```text
myfitnesspalworld/
├── frontend/
├── backend/
├── specs/
├── .github/
│   └── workflows/
├── CLAUDE.md
├── README.md
├── docker-compose.yml
└── .env.example
```

## 6. Architecture Django

```text
backend/
├── accounts/
├── nutrition/
├── diary/
├── recipes/
├── planning/
├── social/
├── progress/
├── ai/
├── notifications/
└── common/
```

## 7. Branding

Direction :

- bleu / blanc ;
- dark mode bleu nuit / gris très sombre ;
- moderne ;
- sobre ;
- santé / nutrition ;
- pas d'esthétique bodybuilder agressive.

Logo :

- silhouette simple d'un homme chauve ;
- aspect professionnel évoquant légèrement un diététicien ;
- logo principal : icône + texte `MyFitnessPalworld` ;
- variante icône seule : favicon / icône PWA.

## 8. Principes produit

- français uniquement ;
- mobile-first ;
- responsive desktop ;
- PWA installable ;
- thème clair, sombre et système ;
- pas de gestion d'exercices dans la V1 ;
- pas de suivi d'eau ;
- offline simple : interface accessible, modifications métier nécessitant Internet ;
- données privées par défaut ;
- compte activé manuellement via Django Admin.
