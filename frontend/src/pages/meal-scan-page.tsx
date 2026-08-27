import { Loader2, Sparkles, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { today } from '@/features/diary/dates'
import { useCreateEntry, useMealTypes } from '@/features/diary/use-diary'
import { Capture } from '@/features/meal-scan/capture'
import { initialLines, loggableLines, type ScanLine } from '@/features/meal-scan/lines'
import { SuggestionCard } from '@/features/meal-scan/suggestion-card'
import { isRunning, useMealScanTask, useStartMealScan } from '@/features/meal-scan/use-meal-scan'
import { ApiError } from '@/lib/api/client'
import type { MealScanSuggestion } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

const AI_DISABLED_MESSAGE =
  'L’analyse par IA est indisponible pour le moment. Le reste de l’application fonctionne normalement : vous pouvez ajouter vos aliments par la recherche.'

/**
 * Meal Scan (spec 01, spec 07 §5).
 *
 * Photo, puis suggestions, puis correction, puis journal. Rien n'est écrit
 * tant que l'utilisateur n'a pas confirmé, et les valeurs nutritionnelles
 * viennent des fiches choisies — jamais de la photo.
 */
export function MealScanPage() {
  const navigate = useNavigate()
  const start = useStartMealScan()
  const create = useCreateEntry()
  const mealTypes = useMealTypes()

  const [taskId, setTaskId] = useState<string | null>(null)
  const task = useMealScanTask(taskId)

  const [date, setDate] = useState(today)
  const [mealTypeId, setMealTypeId] = useState('')
  const [lines, setLines] = useState<ScanLine[]>([])
  const [linesFor, setLinesFor] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const result = task.data?.status === 'success' ? task.data.result : null
  const suggestions: MealScanSuggestion[] = Array.isArray(result?.suggestions)
    ? result.suggestions
    : []

  // Les lignes se déduisent des suggestions, à leur arrivée seulement : les
  // recalculer ensuite effacerait les corrections en cours de saisie.
  if (task.data && task.data.status === 'success' && linesFor !== task.data.id) {
    setLinesFor(task.data.id)
    setLines(initialLines(suggestions))
  }

  const meals = (Array.isArray(mealTypes.data) ? mealTypes.data : []).filter(
    (meal) => meal.is_active,
  )
  const selectedMeal = mealTypeId || String(meals[0]?.id ?? '')

  const analyzing = start.isPending || isRunning(task.data) || (Boolean(taskId) && task.isLoading)
  const failed = task.data?.status === 'failed'
  const aiDisabled = start.error instanceof ApiError && start.error.code === 'ai_disabled'

  const reset = () => {
    setTaskId(null)
    setLinesFor(null)
    setLines([])
    start.reset()
  }

  const analyze = (images: File[]) => {
    start.mutate(images, { onSuccess: (created) => setTaskId(created.id) })
  }

  const confirm = async () => {
    const kept = loggableLines(lines)
    if (kept.length === 0 || selectedMeal === '') return

    setSaving(true)
    try {
      for (const line of kept) {
        await create.mutateAsync({
          date,
          meal_type_id: Number(selectedMeal),
          food_id: line.foodId as number,
          quantity: String(Number(line.quantity.replace(',', '.'))),
          unit_label: line.unit,
        })
      }
      toast.success(
        kept.length === 1 ? 'Aliment ajouté au journal.' : `${kept.length} aliments ajoutés.`,
      )
      navigate('/journal')
    } catch (error) {
      toast.error(describeError(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analyser une photo</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Le modèle reconnaît les aliments et estime les quantités. Les calories, elles, viennent
          toujours de la fiche que vous choisissez.
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

      {start.isError && !aiDisabled && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(start.error)}
        </p>
      )}

      {taskId === null && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Photo du repas</CardTitle>
            <CardDescription>
              Cadrez l’assiette entière. Jusqu’à trois photos sous des angles différents.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Capture onAnalyze={analyze} pending={start.isPending} />
          </CardContent>
        </Card>
      )}

      {taskId !== null && analyzing && (
        <Card>
          <CardContent
            aria-busy="true"
            className="flex items-center gap-3 pt-6 text-sm"
            aria-live="polite"
          >
            <Loader2 aria-hidden="true" className="size-5 animate-spin" />
            <span>Analyse de la photo en cours…</span>
          </CardContent>
        </Card>
      )}

      {failed && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p role="alert" className="text-destructive text-sm">
              {task.data?.error ?? 'L’analyse a échoué.'}
            </p>
            <Button type="button" variant="outline" onClick={reset}>
              Reprendre une photo
            </Button>
          </CardContent>
        </Card>
      )}

      {task.data?.status === 'success' && suggestions.length === 0 && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p className="text-sm">
              Aucun aliment n’a été reconnu sur cette photo. Reprenez-la de plus près, ou ajoutez
              vos aliments par la recherche.
            </p>
            <Button type="button" variant="outline" onClick={reset}>
              Reprendre une photo
            </Button>
          </CardContent>
        </Card>
      )}

      {suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="flex items-center gap-2">
              <Sparkles aria-hidden="true" className="size-4" />
              Aliments détectés
            </CardTitle>
            <CardDescription>
              Corrigez ce qui doit l’être, puis confirmez : rien n’est ajouté au journal avant.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3">
              {suggestions.map((suggestion, index) => {
                const line = lines[index]
                if (!line) return null

                return (
                  <SuggestionCard
                    key={line.key}
                    suggestion={suggestion}
                    line={line}
                    onChange={(next) =>
                      setLines((current) =>
                        current.map((item, position) => (position === index ? next : item)),
                      )
                    }
                    onRemove={() =>
                      setLines((current) =>
                        current.map((item, position) =>
                          position === index ? { ...item, foodId: null, quantity: '0' } : item,
                        ),
                      )
                    }
                  />
                )
              })}
            </ul>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="meal-scan-date">Date</Label>
                <Input
                  id="meal-scan-date"
                  type="date"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              </div>
              <SelectField
                label="Repas"
                value={selectedMeal}
                onChange={(event) => setMealTypeId(event.target.value)}
                options={meals.map((meal) => ({ value: String(meal.id), label: meal.name }))}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={saving || loggableLines(lines).length === 0 || selectedMeal === ''}
                onClick={() => void confirm()}
              >
                {saving && <Loader2 aria-hidden="true" className="size-4 animate-spin" />}
                Ajouter au journal
              </Button>
              <Button type="button" variant="ghost" onClick={reset}>
                Reprendre une photo
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
