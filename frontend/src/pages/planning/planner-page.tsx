import { CalendarPlus, Loader2, Trash2, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AI_DISABLED_MESSAGE, useAIStatus } from '@/features/ai/status'
import { toPayload, type GenerateConstraints } from '@/features/planning/api'
import { fromProposal } from '@/features/planning/day-view'
import { GenerateForm } from '@/features/planning/generate-form'
import { PlanDay } from '@/features/planning/plan-day'
import {
  useDeletePlan,
  useGeneratePlan,
  usePlanProposalTask,
  usePlans,
  useSavePlan,
} from '@/features/planning/use-planning'
import { isRunning } from '@/features/tasks/use-task'
import { ApiError } from '@/lib/api/client'
import { describeError } from '@/lib/query-client'

/**
 * Planification des repas (spec 01 §15).
 *
 * Les identifiants de code restent en anglais — `planning`, `MealPlan` — comme
 * `shopping` sert « Courses ».
 *
 * La génération **ne persiste rien** : elle propose. L'utilisateur relit, puis
 * enregistre — et c'est cet enregistrement qui crée les recettes que le modèle
 * a inventées (spec 07 §8).
 */
export function PlannerPage() {
  const navigate = useNavigate()
  const plans = usePlans()
  const aiStatus = useAIStatus()
  const generate = useGeneratePlan()
  const save = useSavePlan()
  const remove = useDeletePlan()

  const [taskId, setTaskId] = useState<string | null>(null)
  const task = usePlanProposalTask(taskId)
  const [dayIndex, setDayIndex] = useState(0)

  const proposal = task.data?.status === 'success' ? task.data.result : null
  const composing =
    generate.isPending || isRunning(task.data) || (Boolean(taskId) && task.isLoading)
  const failed = task.data?.status === 'failed'
  const aiDisabled =
    aiStatus.data?.enabled === false ||
    (generate.error instanceof ApiError && generate.error.code === 'ai_disabled')

  const rows = Array.isArray(plans.data?.results) ? plans.data.results : []
  const newRecipes = proposal
    ? [
        ...new Set(
          proposal.days.flatMap((day) =>
            day.meals.flatMap((meal) =>
              meal.items.filter((item) => item.new_recipe).map((item) => item.label),
            ),
          ),
        ),
      ]
    : []

  const reset = () => {
    setTaskId(null)
    setDayIndex(0)
    generate.reset()
  }

  const compose = (constraints: GenerateConstraints) => {
    generate.mutate(constraints, { onSuccess: (created) => setTaskId(created.id) })
  }

  const keep = () => {
    if (!proposal) return

    save.mutate(toPayload(proposal, proposal.days), {
      onSuccess: (plan) => {
        toast.success('Planification enregistrée.')
        navigate(`/planification/${plan.id}`)
      },
      onError: (error) => toast.error(describeError(error)),
    })
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Planification</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Le modèle compose ; les calories, elles, viennent des fiches de la base. C’est sur elles
          que l’écart aux objectifs est mesuré.
        </p>
      </div>

      {aiDisabled && (
        <Card>
          <CardContent className="flex gap-3 pt-6 text-sm">
            <TriangleAlert aria-hidden="true" className="text-muted-foreground size-5 shrink-0" />
            <p>{AI_DISABLED_MESSAGE}</p>
          </CardContent>
        </Card>
      )}

      {generate.isError && !aiDisabled && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(generate.error)}
        </p>
      )}

      {taskId === null && !aiDisabled && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Composer une planification</CardTitle>
            <CardDescription>
              Les objectifs de chaque journée sont repris de vos objectifs, surcharge de jour de
              semaine comprise.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <GenerateForm onGenerate={compose} pending={generate.isPending} />
          </CardContent>
        </Card>
      )}

      {taskId !== null && composing && (
        <Card>
          <CardContent
            aria-busy="true"
            aria-live="polite"
            className="flex items-center gap-3 pt-6 text-sm"
          >
            <Loader2 aria-hidden="true" className="size-5 animate-spin" />
            <span>
              Composition en cours… {task.data?.progress ? `${task.data.progress} %` : ''}
            </span>
          </CardContent>
        </Card>
      )}

      {failed && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p role="alert" className="text-destructive text-sm">
              {task.data?.error ?? 'La composition a échoué.'}
            </p>
            <Button type="button" variant="outline" onClick={reset}>
              Recommencer
            </Button>
          </CardContent>
        </Card>
      )}

      {proposal && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Proposition</CardTitle>
            <CardDescription>
              Rien n’est enregistré tant que vous n’avez pas validé.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {proposal.warnings.length > 0 && (
              <ul className="text-muted-foreground space-y-1 text-sm">
                {proposal.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}

            {newRecipes.length > 0 && (
              <p className="text-sm">
                {newRecipes.length === 1
                  ? 'Une recette sera ajoutée à vos recettes : '
                  : `${newRecipes.length} recettes seront ajoutées à vos recettes : `}
                {newRecipes.join(', ')}.
              </p>
            )}

            {proposal.days[dayIndex] && (
              <PlanDay
                day={fromProposal(proposal.days[dayIndex])}
                index={dayIndex}
                total={proposal.days.length}
                onPrevious={() => setDayIndex((current) => Math.max(0, current - 1))}
                onNext={() =>
                  setDayIndex((current) => Math.min(proposal.days.length - 1, current + 1))
                }
              />
            )}

            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={save.isPending} onClick={keep}>
                {save.isPending && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
                Enregistrer cette planification
              </Button>
              <Button type="button" variant="ghost" onClick={reset}>
                Recommencer
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle as="h2">Mes planifications</CardTitle>
        </CardHeader>
        <CardContent>
          {plans.isLoading ? (
            <div aria-busy="true" className="bg-muted h-16 animate-pulse rounded-lg" />
          ) : rows.length === 0 ? (
            <p className="text-muted-foreground text-sm">Aucune planification pour le moment.</p>
          ) : (
            <ul className="divide-y">
              {rows.map((plan) => (
                <li key={plan.id} className="flex items-center justify-between gap-3 py-2">
                  <Link to={`/planification/${plan.id}`} className="flex-1 text-sm hover:underline">
                    <span className="font-medium">{plan.name}</span>
                    <span className="text-muted-foreground ml-2">
                      {plan.days_count} jour{plan.days_count > 1 ? 's' : ''}
                    </span>
                  </Link>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Supprimer ${plan.name}`}
                    onClick={() => remove.mutate(plan.id)}
                  >
                    <Trash2 aria-hidden="true" className="size-4" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <p className="text-muted-foreground flex items-center gap-2 text-xs">
        <CalendarPlus aria-hidden="true" className="size-3.5" />
        Une planification est une intention : elle se supprime franchement, et le journal qu’on en
        tire lui survit.
      </p>
    </div>
  )
}
