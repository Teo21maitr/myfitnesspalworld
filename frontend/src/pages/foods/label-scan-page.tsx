import { Loader2, ScanText, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AI_DISABLED_MESSAGE, useAIStatus } from '@/features/ai/status'
import { Capture } from '@/features/camera/capture'
import { FoodForm } from '@/features/foods/food-form'
import { describeUnreadable } from '@/features/label-scan/nutrients'
import { useLabelScanTask, useStartLabelScan } from '@/features/label-scan/use-label-scan'
import { isRunning } from '@/features/tasks/use-task'
import { ApiError } from '@/lib/api/client'
import { describeError } from '@/lib/query-client'

/**
 * Création d'un aliment à partir de son étiquette (spec 01 §11).
 *
 * Le modèle **recopie** le tableau nutritionnel ; il n'estime rien. Ce qu'il
 * n'a pas lu reste vide et l'écran le dit, plutôt que de laisser un champ vide
 * passer pour un oubli de saisie.
 *
 * Rien n'est enregistré avant que l'utilisateur ne valide le formulaire : le
 * brouillon ne fait que le préremplir.
 */
export function LabelScanPage() {
  const start = useStartLabelScan()
  const aiStatus = useAIStatus()

  const [taskId, setTaskId] = useState<string | null>(null)
  const task = useLabelScanTask(taskId)

  const result = task.data?.status === 'success' ? task.data.result : null
  const analyzing = start.isPending || isRunning(task.data) || (Boolean(taskId) && task.isLoading)
  const failed = task.data?.status === 'failed'
  const aiDisabled =
    aiStatus.data?.enabled === false ||
    (start.error instanceof ApiError && start.error.code === 'ai_disabled')

  const reset = () => {
    setTaskId(null)
    start.reset()
  }

  const analyze = (images: File[]) => {
    start.mutate(images, { onSuccess: (created) => setTaskId(created.id) })
  }

  const missing = result ? describeUnreadable(result.unreadable) : ''

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Créer depuis une étiquette</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Photographiez le tableau nutritionnel. Les valeurs sont recopiées telles quelles, jamais
          estimées — vérifiez-les avant d’enregistrer.
        </p>
      </div>

      {aiDisabled && (
        <Card>
          <CardContent className="flex gap-3 pt-6 text-sm">
            <TriangleAlert aria-hidden="true" className="text-muted-foreground size-5 shrink-0" />
            <div className="space-y-2">
              <p>{AI_DISABLED_MESSAGE}</p>
              <Link to="/mes-aliments" className="text-primary inline-block underline">
                Créer un aliment à la main
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {start.isError && !aiDisabled && (
        <p role="alert" className="text-destructive text-sm">
          {describeError(start.error)}
        </p>
      )}

      {taskId === null && !aiDisabled && (
        <Card>
          <CardHeader>
            <CardTitle as="h2">Photo de l’étiquette</CardTitle>
            <CardDescription>
              Cadrez le tableau « pour 100 g » ou « pour 100 ml », celui que l’étiquette porte
              obligatoirement.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Capture
              onAnalyze={analyze}
              pending={start.isPending}
              subject="de l’étiquette"
              analyzeLabel="Lire l’étiquette"
            />
          </CardContent>
        </Card>
      )}

      {taskId !== null && analyzing && (
        <Card>
          <CardContent
            aria-busy="true"
            aria-live="polite"
            className="flex items-center gap-3 pt-6 text-sm"
          >
            <Loader2 aria-hidden="true" className="size-5 animate-spin" />
            <span>Lecture de l’étiquette en cours…</span>
          </CardContent>
        </Card>
      )}

      {failed && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p role="alert" className="text-destructive text-sm">
              {task.data?.error ?? 'La lecture a échoué.'}
            </p>
            <Button type="button" variant="outline" onClick={reset}>
              Reprendre une photo
            </Button>
          </CardContent>
        </Card>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle as="h2" className="flex items-center gap-2">
              <ScanText aria-hidden="true" className="size-4" />
              Ce que la photo a donné
            </CardTitle>
            <CardDescription>
              Vérifiez chaque valeur avant d’enregistrer : c’est vous qui créez cet aliment.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.basis === 'unknown' && (
              <p className="text-destructive text-sm">
                Aucune colonne « pour 100 g » ou « pour 100 ml » n’a été trouvée sur la photo.
                Aucune valeur n’a donc été reprise : une colonne « par portion » recopiée telle
                quelle fausserait tout. Reprenez la photo, ou saisissez les valeurs vous-même.
              </p>
            )}

            {missing && result.basis !== 'unknown' && (
              <p className="text-muted-foreground text-sm">
                La photo n’a pas donné : {missing}. Ces champs restent vides — ils ne sont pas
                ramenés à zéro.
              </p>
            )}

            <FoodForm draft={result.draft} />

            <Button type="button" variant="ghost" onClick={reset}>
              Reprendre une photo
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
