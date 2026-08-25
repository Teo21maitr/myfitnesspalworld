import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { FormError } from '@/components/form/form-error'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { meQueryKey } from '@/features/auth/api'
import { useApiFormErrors } from '@/features/auth/use-api-form-errors'
import { currentGoalQueryKey, goalsQueryKey, submitOnboarding } from '@/features/nutrition/api'

import { EMPTY_DRAFT, STEPS, onboardingSchema, type OnboardingValues } from './schema'
import { Stepper } from './stepper'
import { ActivityStep } from './steps/activity-step'
import { CaloriesStep } from './steps/calories-step'
import { GoalStep } from './steps/goal-step'
import { MacrosStep } from './steps/macros-step'
import { ProfileStep } from './steps/profile-step'
import { RateStep } from './steps/rate-step'
import { SummaryStep } from './steps/summary-step'
import { toCalculationPayload } from './use-calorie-estimate'

const DRAFT_KEY = 'mfp-onboarding-draft'

/** Relit le brouillon pour qu'un rafraîchissement ne perde pas la saisie. */
function readDraft(): OnboardingValues {
  if (typeof window === 'undefined') return EMPTY_DRAFT

  try {
    const stored = window.sessionStorage.getItem(DRAFT_KEY)
    return stored ? { ...EMPTY_DRAFT, ...(JSON.parse(stored) as OnboardingValues) } : EMPTY_DRAFT
  } catch {
    return EMPTY_DRAFT
  }
}

const STEP_COMPONENTS = {
  profil: ProfileStep,
  objectif: GoalStep,
  activite: ActivityStep,
  rythme: RateStep,
  calories: CaloriesStep,
  macros: MacrosStep,
  resume: SummaryStep,
} as const

export function OnboardingWizard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [index, setIndex] = useState(0)

  const form = useForm<OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: readDraft(),
    mode: 'onTouched',
  })

  const { control, formState, setError, trigger, getValues } = form
  const { formError, setFormError, handleApiError } = useApiFormErrors<OnboardingValues>(setError)

  // Sauvegarde continue du brouillon. `useWatch` est préféré à `watch()` :
  // ce dernier renvoie une fonction non mémoïsable.
  const draft = useWatch({ control })
  useEffect(() => {
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  }, [draft])

  const mutation = useMutation({
    mutationFn: submitOnboarding,
    onSuccess: (result) => {
      window.sessionStorage.removeItem(DRAFT_KEY)
      queryClient.invalidateQueries({ queryKey: meQueryKey })
      queryClient.invalidateQueries({ queryKey: goalsQueryKey })
      queryClient.invalidateQueries({ queryKey: currentGoalQueryKey })
      result.warnings.forEach((warning) => toast.warning(warning))
      toast.success('Vos objectifs sont enregistrés.')
      navigate('/', { replace: true })
    },
    onError: (error) => handleApiError(error, ['daily_calories', 'birth_date', 'target_weight_kg']),
  })

  const step = STEPS[index]
  if (!step) return null

  const StepComponent = STEP_COMPONENTS[step.id]
  const isLast = index === STEPS.length - 1

  const goNext = async () => {
    setFormError(undefined)
    const valid = await trigger(step.fields.length ? [...step.fields] : undefined)
    if (valid) setIndex((current) => Math.min(current + 1, STEPS.length - 1))
  }

  const goBack = () => {
    setFormError(undefined)
    setIndex((current) => Math.max(current - 1, 0))
  }

  const submit = async () => {
    setFormError(undefined)
    if (!(await trigger())) return

    const values = getValues()
    await mutation
      .mutateAsync({
        ...toCalculationPayload(values),
        daily_calories: values.daily_calories,
        protein_g: values.protein_g,
        carbs_g: values.carbs_g,
        fat_g: values.fat_g,
        calories_source: 'calculated',
        macros_source: 'calculated',
      })
      .catch(() => undefined)
  }

  return (
    <Card>
      <CardHeader className="gap-4">
        <CardTitle as="h1" className="text-xl">
          Configurons vos objectifs
        </CardTitle>
        <Stepper currentIndex={index} />
      </CardHeader>

      <CardContent>
        <FormProvider {...form}>
          {/* La soumission est pilotée par les boutons : la touche Entrée ne
              doit pas valider un parcours incomplet. */}
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault()
            }}
            className="flex flex-col gap-6"
          >
            <FormError message={formError} />

            <StepComponent />

            <div className="flex items-center justify-between gap-3">
              <Button type="button" variant="ghost" onClick={goBack} disabled={index === 0}>
                <ArrowLeft aria-hidden="true" />
                Retour
              </Button>

              {isLast ? (
                <Button
                  type="button"
                  onClick={submit}
                  disabled={mutation.isPending || formState.isSubmitting}
                >
                  {mutation.isPending ? 'Enregistrement…' : 'Terminer'}
                </Button>
              ) : (
                <Button type="button" onClick={goNext}>
                  Continuer
                  <ArrowRight aria-hidden="true" />
                </Button>
              )}
            </div>
          </form>
        </FormProvider>
      </CardContent>
    </Card>
  )
}
