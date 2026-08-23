# 10 — Conventions de développement

## 1. Versions

Au bootstrap du projet :

- sélectionner des versions stables compatibles ;
- verrouiller les dépendances ;
- ne pas utiliser automatiquement `latest` en production.

Frontend :

- `package-lock.json` obligatoire.

Backend :

- `pyproject.toml` + lock adapté ou `requirements.txt` verrouillé.

## 2. Python

- code typé quand utile ;
- fonctions métier petites et testables ;
- views DRF fines ;
- logique métier dans services ;
- accès externe dans clients/adapters ;
- pas de logique lourde dans serializers ;
- `Decimal`, jamais float, pour nutrition persistée.

## 3. Django

- custom User dès première migration ;
- app boundaries respectées ;
- contraintes DB quand possible ;
- indexes explicites sur recherches fréquentes ;
- transactions pour opérations multi-modèles ;
- `select_related/prefetch_related` sur endpoints de listes ;
- migrations backward-compatible autant que possible.

## 4. PostgreSQL

Recommandé :

- extension `pg_trgm` ;
- indexes trigram pour recherche ;
- unique case-insensitive username ;
- indexes `(user, date)` ;
- indexes sharing/owner/status ;
- contraintes check sur quantités non négatives pertinentes.

## 5. API

- `/api/v1/`;
- erreurs cohérentes ;
- validation serveur ;
- sérialisation explicitement contrôlée ;
- ne pas exposer des champs internes inutiles ;
- pagination 25 par défaut ;
- status codes HTTP corrects.

Format erreur recommandé :

```json
{
  "code": "validation_error",
  "message": "Données invalides.",
  "errors": {
    "field": ["..."]
  }
}
```

## 6. TypeScript

- strict mode ;
- pas de `any` sans justification ;
- types API centralisés ;
- validation Zod des formulaires et, si utile, des réponses critiques ;
- hooks dédiés aux queries/mutations.

## 7. State management

Priorité :

- server state : TanStack Query ;
- local UI state : React ;
- context seulement pour cross-cutting stable ;
- ne pas ajouter Redux sans besoin réel.

## 8. CSS/UI

- Tailwind ;
- composants réutilisables ;
- shadcn/ui ;
- tokens de couleurs ;
- dark mode dès le début ;
- responsive dès la première implémentation.

## 9. Git

Branches :

- develop
- main

Pas de branche feature obligatoire.

Commits :

```text
feat(scope): description
fix(scope): description
refactor(scope): description
test(scope): description
docs(scope): description
chore(scope): description
perf(scope): description
```

## 10. Migrations

Règle stricte :

> Une migration appliquée n'est jamais modifiée.

Créer une nouvelle migration.

Éviter :

- renommage + suppression + transformation destructive en une seule release ;
- longue migration bloquante sans analyse ;
- dépendance code nouveau uniquement avant migration effective.

## 11. Secrets

`.env` ignoré.

`.env.example` :

- exhaustif ;
- aucune vraie valeur secrète.

## 12. Erreurs

Ne jamais masquer silencieusement une erreur métier.

Frontend :

- message utilisateur compréhensible ;
- détail technique non sensible si dev.

Backend :

- log technique nettoyé ;
- réponse standardisée.

## 13. Performance

D'abord :

- N+1 ;
- indexes ;
- pagination ;
- cache externe ;
- tâches async.

Ne pas optimiser prématurément sans mesure.

## 14. Documentation

Toute modification de contrat API, règle métier, variable d'environnement ou workflow de déploiement doit mettre à jour les specs concernées.
