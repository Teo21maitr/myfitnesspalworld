import { ChefHat, Plus, Star, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { NutrientValue } from '@/features/foods/nutrient-value'
import { useRecipes, useToggleRecipeFavorite } from '@/features/recipes/use-recipes'
import type { RecipeListItem } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

function RecipeRow({ recipe }: { recipe: RecipeListItem }) {
  const toggleFavorite = useToggleRecipeFavorite()

  return (
    <li className="flex items-center gap-2 border-b last:border-b-0">
      <Link
        to={`/recettes/${recipe.id}`}
        className="hover:bg-accent -mx-2 flex flex-1 flex-col gap-0.5 rounded-md px-2 py-3"
      >
        <span className="font-medium">{recipe.name}</span>
        <span className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
          <span>
            <NutrientValue value={recipe.nutrition?.energy_kcal ?? null} unit="kcal" /> par portion
            {/* Le chiffre est sous-évalué si un ingrédient n'a pas d'énergie. */}
            {recipe.nutrition?.incomplete_nutrients.includes('energy_kcal') && ' (partiel)'}
          </span>
          <span aria-hidden="true">·</span>
          <span>
            {Number(recipe.servings).toLocaleString('fr-FR')} portion
            {Number(recipe.servings) > 1 ? 's' : ''}
          </span>
          <span aria-hidden="true">·</span>
          <span>
            {recipe.ingredient_count} ingrédient{recipe.ingredient_count > 1 ? 's' : ''}
          </span>
        </span>
      </Link>

      {recipe.is_editable && (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label={
            recipe.is_favorite
              ? `Retirer ${recipe.name} des favoris`
              : `Ajouter ${recipe.name} aux favoris`
          }
          aria-pressed={recipe.is_favorite}
          onClick={() => toggleFavorite.mutate({ id: recipe.id, isFavorite: recipe.is_favorite })}
        >
          <Star
            aria-hidden="true"
            className={recipe.is_favorite ? 'fill-primary text-primary size-4' : 'size-4'}
          />
        </Button>
      )}
    </li>
  )
}

/** Liste des recettes (spec 01 §14). */
export function RecipesPage() {
  const { data, error, isPending } = useRecipes()
  const recipes = Array.isArray(data?.results) ? data.results : []

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Recettes</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Des ingrédients préparés ensemble, puis divisés en portions.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/recettes/nouvelle">
            <Plus aria-hidden="true" className="size-4" />
            Nouvelle
          </Link>
        </Button>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-24 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement des recettes…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {data && recipes.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="text-base">
              Aucune recette
            </CardTitle>
            <CardDescription>
              Créez-en une pour journaliser un plat entier en une fois, au lieu de ressaisir chaque
              ingrédient.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to="/recettes/nouvelle">
                <ChefHat aria-hidden="true" className="size-4" />
                Créer une recette
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {recipes.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <ul className="flex flex-col">
              {recipes.map((recipe) => (
                <RecipeRow key={recipe.id} recipe={recipe} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
