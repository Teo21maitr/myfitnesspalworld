import { ArrowLeft, TriangleAlert } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RecipeForm } from '@/features/recipes/recipe-form'
import { useRecipe, useUpdateRecipe } from '@/features/recipes/use-recipes'
import { describeError } from '@/lib/query-client'

export function EditRecipePage() {
  const params = useParams()
  const navigate = useNavigate()
  const id = Number(params.id)

  const { data: recipe, error, isPending } = useRecipe(id)
  // Identifiant non numérique : la requête est désactivée et ne se
  // résoudra jamais. Sans ce cas, l'écran resterait en chargement.
  const isUnknown = !Number.isFinite(id)
  const update = useUpdateRecipe(id)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to={`/recettes/${id}`}>
            <ArrowLeft aria-hidden="true" />
            Retour
          </Link>
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Modifier la recette</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Les entrées déjà journalisées gardent leurs valeurs : une modification n’est jamais
          rétroactive.
        </p>
      </div>

      {isPending && !isUnknown && (
        <div aria-busy="true">
          <div className="bg-muted h-40 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement de la recette…</span>
        </div>
      )}

      {(error || isUnknown) && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error ? describeError(error) : 'Recette introuvable.'}
        </p>
      )}

      {recipe && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Composition</CardTitle>
          </CardHeader>
          <CardContent>
            <RecipeForm
              recipe={recipe}
              isPending={update.isPending}
              error={update.error}
              submitLabel="Enregistrer"
              onSubmit={(payload) =>
                update.mutate(payload, {
                  onSuccess: () => {
                    toast.success('Recette mise à jour.')
                    void navigate(`/recettes/${id}`)
                  },
                })
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
