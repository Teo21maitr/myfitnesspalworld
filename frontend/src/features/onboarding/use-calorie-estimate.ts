import { useMutation } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useFormContext } from 'react-hook-form'

import { calculateCalories, type CalculationPayload } from '@/features/nutrition/api'

import type { OnboardingValues } from './schema'

/** Traduit les valeurs du formulaire en payload attendu par le backend. */
export function toCalculationPayload(values: OnboardingValues): CalculationPayload {
  return {
    birth_date: values.birth_date,
    sex_for_calculation: values.sex_for_calculation,
    height_cm: values.height_cm,
    weight_kg: values.weight_kg,
    activity_level: values.activity_level,
    goal_type: values.goal_type,
    goal_rate_kg_per_week: values.goal_rate_kg_per_week || null,
    target_weight_kg: values.target_weight_kg || null,
  }
}

/**
 * Lance le calcul côté serveur à l'arrivée sur l'étape « Calories ».
 *
 * La formule n'est jamais dupliquée en TypeScript : le backend reste la seule
 * source de vérité pour les calories (spec 05 §12).
 */
export function useCalorieEstimate() {
  const { getValues } = useFormContext<OnboardingValues>()
  const mutation = useMutation({ mutationFn: calculateCalories })

  const { mutate } = mutation

  useEffect(() => {
    mutate(toCalculationPayload(getValues()))
  }, [mutate, getValues])

  return mutation
}
