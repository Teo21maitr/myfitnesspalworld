import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RecipeForm } from '@/features/recipes/recipe-form'
import { useCreateRecipe } from '@/features/recipes/use-recipes'

export function NewRecipePage() {
  const navigate = useNavigate()
  const create = useCreateRecipe()

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/recettes">
            <ArrowLeft aria-hidden="true" />
            Recettes
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Nouvelle recette</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Composition</CardTitle>
        </CardHeader>
        <CardContent>
          <RecipeForm
            isPending={create.isPending}
            error={create.error}
            submitLabel="Créer la recette"
            onSubmit={(payload) =>
              create.mutate(payload, {
                onSuccess: (recipe) => {
                  toast.success('Recette créée.')
                  void navigate(`/recettes/${recipe.id}`)
                },
              })
            }
          />
        </CardContent>
      </Card>
    </div>
  )
}
