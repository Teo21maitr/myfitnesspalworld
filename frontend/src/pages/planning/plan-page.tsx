import { Loader2, ShoppingCart, Utensils } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { activeMeals } from '@/features/diary/meals'
import { useMealTypes } from '@/features/diary/use-diary'
import { fromPlan } from '@/features/planning/day-view'
import { PlanDay } from '@/features/planning/plan-day'
import { useAddPlanToDiary, usePlan, useRegenerateMeal } from '@/features/planning/use-planning'
import { useGenerateShoppingList } from '@/features/shopping/use-shopping'
import { describeError } from '@/lib/query-client'

/**
 * Une planification enregistrée (spec 01 §15).
 *
 * L'ajout au journal **n'écrase jamais** : un repas déjà rempli est nommé, et
 * l'ajout attend une confirmation explicite.
 */
export function PlanPage() {
  const { id } = useParams()
  const planId = Number(id)
  const navigate = useNavigate()

  const plan = usePlan(planId)
  const mealTypes = useMealTypes()
  const regenerate = useRegenerateMeal(planId)
  const addToDiary = useAddPlanToDiary(planId)
  const generateList = useGenerateShoppingList()

  const [dayIndex, setDayIndex] = useState(0)
  const [conflicts, setConflicts] = useState<string[] | null>(null)
  const [regenerating, setRegenerating] = useState<number | null>(null)

  const meals = activeMeals(mealTypes.data)
  const days = plan.data?.days ?? []
  const current = days[dayIndex]

  if (plan.isLoading) {
    return (
      <div aria-busy="true" className="mx-auto w-full max-w-2xl">
        <div className="bg-muted h-64 animate-pulse rounded-xl" />
      </div>
    )
  }

  if (plan.isError || !plan.data) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p role="alert" className="text-destructive text-sm">
          {describeError(plan.error)}
        </p>
      </div>
    )
  }

  const journal = (confirm: boolean) => {
    addToDiary.mutate(confirm, {
      onSuccess: (result) => {
        if (result.conflicts.length > 0 && result.entries.length === 0) {
          setConflicts(result.conflicts)
          return
        }
        setConflicts(null)
        toast.success(
          result.skipped.length > 0
            ? `Ajouté au journal. Non repris : ${result.skipped.join(', ')}.`
            : 'Planification ajoutée au journal.',
        )
        navigate('/journal')
      },
      onError: (error) => toast.error(describeError(error)),
    })
  }

  const toShoppingList = () => {
    generateList.mutate(
      { meal_plan_id: planId, name: `Courses — ${plan.data.name}` },
      {
        onSuccess: (list) => navigate(`/courses/${list.id}`),
        onError: (error) => toast.error(describeError(error)),
      },
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{plan.data.name}</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {plan.data.days_count} jour{plan.data.days_count > 1 ? 's' : ''}, du{' '}
          {new Date(`${plan.data.start_date}T12:00:00`).toLocaleDateString('fr-FR')} au{' '}
          {new Date(`${plan.data.end_date}T12:00:00`).toLocaleDateString('fr-FR')}.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          {current && (
            <PlanDay
              day={fromPlan(current, meals)}
              index={dayIndex}
              total={days.length}
              onPrevious={() => setDayIndex((current) => Math.max(0, current - 1))}
              onNext={() => setDayIndex((current) => Math.min(days.length - 1, current + 1))}
              regenerating={regenerate.isPending ? regenerating : null}
              onRegenerate={(mealTypeId) => {
                setRegenerating(mealTypeId)
                regenerate.mutate(
                  { day_id: current.id, meal_type_id: mealTypeId },
                  {
                    onSettled: () => setRegenerating(null),
                    onError: (error) => toast.error(describeError(error)),
                  },
                )
              }}
            />
          )}
        </CardContent>
      </Card>

      {conflicts && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Ces repas contiennent déjà quelque chose</CardTitle>
            <CardDescription>
              Rien ne sera remplacé : le planning s’ajoutera par-dessus.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="text-muted-foreground list-inside list-disc text-sm">
              {conflicts.map((conflict) => (
                <li key={conflict}>{conflict}</li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={() => journal(true)} disabled={addToDiary.isPending}>
                Ajouter quand même
              </Button>
              <Button type="button" variant="ghost" onClick={() => setConflicts(null)}>
                Annuler
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={addToDiary.isPending} onClick={() => journal(false)}>
          {addToDiary.isPending ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Utensils aria-hidden="true" className="size-4" />
          )}
          Ajouter au journal
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={generateList.isPending}
          onClick={toShoppingList}
        >
          {generateList.isPending ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <ShoppingCart aria-hidden="true" className="size-4" />
          )}
          Liste de courses
        </Button>
        <Button asChild type="button" variant="ghost">
          <Link to="/planification">Toutes les planifications</Link>
        </Button>
      </div>
    </div>
  )
}
