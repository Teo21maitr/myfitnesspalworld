# 07 — IA et intégrations

## 1. Règle fondamentale

L'IA accélère la saisie et la génération.

Elle n'est jamais la source nutritionnelle de vérité.

Les calories/macros affichées au journal sont calculées à partir de données structurées de la base.

## 2. Architecture

Interface :

```text
AIService
├── analyze_meal()
├── parse_voice_log()
├── generate_meal_plan()
└── generate_recipe()
```

Provider initial :

`AnthropicProvider`

Prévoir la possibilité d'ajouter :

- OpenAIProvider
- GeminiProvider
- autre

sans réécrire les services métier.

## 3. Variables

```text
ANTHROPIC_API_KEY=
AI_MEAL_SCAN_MODEL=
AI_MEAL_PLANNER_MODEL=
AI_VOICE_PARSING_MODEL=
AI_RECIPE_MODEL=
```

Le modèle n'est jamais codé en dur.

## 4. Sorties structurées

Toutes les réponses IA doivent :

1. avoir un schéma attendu ;
2. être parsées ;
3. être validées côté backend ;
4. être rejetées si invalides ;
5. ne jamais être exécutées ou persistées aveuglément.

Pydantic ou validation équivalente recommandée.

## 5. Meal Scan

Entrée :

- une ou plusieurs images.

Sortie logique :

```json
[
  {
    "label": "Poulet grillé",
    "estimated_quantity": 150,
    "unit": "g",
    "confidence": 0.84,
    "alternatives": []
  }
]
```

L'IA peut :

- identifier plusieurs aliments ;
- proposer plusieurs hypothèses ;
- estimer les quantités.

Ensuite :

1. backend recherche les correspondances nutritionnelles ;
2. UI affiche les suggestions ;
3. utilisateur corrige ;
4. utilisateur confirme ;
5. journal normal crée les snapshots.

Si aucune correspondance fiable :

- proposer recherche manuelle ;
- éventuellement proposer création d'aliment générique ;
- validation utilisateur obligatoire.

Photos :

- temporaires ;
- supprimées juste après traitement ;
- jamais conservées par défaut.

Quota applicatif : illimité pour l'utilisateur, mais conserver un kill switch admin global.

## 6. Voice Logging

Langue : français.

Pipeline :

```text
audio
→ speech-to-text
→ texte
→ AIService.parse_voice_log
→ aliments structurés
→ confirmation
→ journal
```

Fournisseur speech-to-text configurable.

Exemple :

> J'ai mangé 200 g de riz, 150 g de poulet et une pomme.

Résultat :

- riz 200 g ;
- poulet 150 g ;
- pomme 1 unité.

Audio :

- temporaire ;
- supprimé après transcription/traitement.

## 7. Meal Planner

Entrées :

- période ;
- objectifs ;
- nombre de repas ;
- allergies ;
- aliments aimés ;
- aliments détestés ;
- recettes personnelles ;
- aliments fréquents.

Le modèle propose les repas.

Le backend résout les aliments/recettes dans la base et calcule les valeurs réelles.

Tolérances :

- calories ±5 % ;
- protéines ±10 % ;
- glucides ±10 % ;
- lipides ±10 %.

Si hors tolérance :

- demander correction/génération ;
- maximum 3 essais ;
- sinon retourner le meilleur résultat avec avertissement.

## 8. Recettes IA

Une recette inventée par IA :

- reste une proposition ;
- ingrédients résolus dans la base ;
- nutrition calculée par backend ;
- utilisateur valide avant enregistrement.

## 9. Tâches async

Meal Scan, Voice, Planner et rapports lourds passent par Celery.

API générique de statut :

```text
GET /api/v1/tasks/{id}/
```

## 10. Logs IA

Stocker :

- utilisateur id ;
- type tâche ;
- provider ;
- model ;
- statut ;
- durée ;
- erreur nettoyée ;
- coût approximatif si calculable.

Ne pas stocker durablement :

- image brute ;
- audio brut ;
- secret ;
- prompt contenant inutilement des données privées.

## 11. Résilience

Si l'IA est indisponible :

- Meal Scan / Voice / Planner affichent une erreur claire ;
- le reste de l'application fonctionne normalement.

Un admin peut désactiver globalement l'IA.
