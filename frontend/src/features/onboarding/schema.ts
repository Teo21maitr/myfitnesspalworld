import { z } from 'zod'

import type { CardOption } from '@/components/form/option-cards'
import type { SelectOption } from '@/components/form/select-field'
import type { ActivityLevel, GoalType, SexForCalculation } from '@/lib/api/types'

/**
 * Validation du parcours d'onboarding.
 *
 * Les nombres sont manipulés en chaînes : c'est ce que renvoie un `<input>` et
 * ce qu'attend l'API, qui sérialise ses décimales en chaînes pour ne perdre
 * aucune précision.
 */

interface DecimalOptions {
  label: string
  min: number
  max: number
  required?: boolean
}

function decimalField({ label, min, max, required = true }: DecimalOptions) {
  const base = z
    .string()
    .trim()
    .refine((value) => value === '' || !Number.isNaN(Number(value)), {
      message: `${label} doit être un nombre.`,
    })
    .refine((value) => value === '' || Number(value) >= min, {
      message: `${label} doit être d’au moins ${min}.`,
    })
    .refine((value) => value === '' || Number(value) <= max, {
      message: `${label} ne peut pas dépasser ${max}.`,
    })

  if (!required) return base

  return base.refine((value) => value !== '', { message: `${label} est obligatoire.` })
}

export const MINIMUM_AGE = 18

function ageOn(birthDate: Date, reference: Date): number {
  let years = reference.getFullYear() - birthDate.getFullYear()
  const beforeBirthday =
    reference.getMonth() < birthDate.getMonth() ||
    (reference.getMonth() === birthDate.getMonth() && reference.getDate() < birthDate.getDate())
  if (beforeBirthday) years -= 1
  return years
}

export const onboardingSchema = z
  .object({
    // Étape 1 — profil
    birth_date: z
      .string()
      .min(1, 'La date de naissance est obligatoire.')
      .refine((value) => !Number.isNaN(Date.parse(value)), { message: 'Date invalide.' })
      .refine((value) => new Date(value) <= new Date(), {
        message: 'La date de naissance ne peut pas être dans le futur.',
      })
      .refine((value) => ageOn(new Date(value), new Date()) >= MINIMUM_AGE, {
        message: `L’application est réservée aux personnes de ${MINIMUM_AGE} ans et plus.`,
      }),
    sex_for_calculation: z.enum(['FEMALE', 'MALE'], {
      message: 'Choisissez une option pour le calcul.',
    }),
    height_cm: decimalField({ label: 'La taille', min: 100, max: 250 }),
    weight_kg: decimalField({ label: 'Le poids', min: 30, max: 400 }),

    // Étape 2 — objectif
    goal_type: z.enum(['LOSS', 'MAINTENANCE', 'GAIN'], { message: 'Choisissez un objectif.' }),
    target_weight_kg: decimalField({
      label: 'Le poids cible',
      min: 30,
      max: 400,
      required: false,
    }),

    // Étape 3 — activité
    activity_level: z.enum(
      ['SEDENTARY', 'LIGHTLY_ACTIVE', 'MODERATELY_ACTIVE', 'VERY_ACTIVE', 'EXTREMELY_ACTIVE'],
      { message: 'Choisissez un niveau d’activité.' },
    ),

    // Étape 4 — rythme
    goal_rate_kg_per_week: decimalField({
      label: 'Le rythme',
      min: 0,
      max: 2,
      required: false,
    }),

    // Étape 5 — calories
    daily_calories: decimalField({ label: 'L’objectif calorique', min: 500, max: 10000 }),

    // Étape 6 — macros
    protein_g: decimalField({ label: 'Les protéines', min: 0, max: 1000 }),
    carbs_g: decimalField({ label: 'Les glucides', min: 0, max: 1000 }),
    fat_g: decimalField({ label: 'Les lipides', min: 0, max: 1000 }),
  })
  .superRefine((values, ctx) => {
    // Un rythme est nécessaire dès que le poids doit bouger.
    if (values.goal_type !== 'MAINTENANCE' && !values.goal_rate_kg_per_week) {
      ctx.addIssue({
        code: 'custom',
        path: ['goal_rate_kg_per_week'],
        message: 'Choisissez un rythme.',
      })
    }

    if (!values.target_weight_kg || !values.weight_kg) return

    const target = Number(values.target_weight_kg)
    const current = Number(values.weight_kg)

    if (values.goal_type === 'LOSS' && target >= current) {
      ctx.addIssue({
        code: 'custom',
        path: ['target_weight_kg'],
        message: 'Un objectif de perte demande un poids cible inférieur.',
      })
    }
    if (values.goal_type === 'GAIN' && target <= current) {
      ctx.addIssue({
        code: 'custom',
        path: ['target_weight_kg'],
        message: 'Un objectif de prise demande un poids cible supérieur.',
      })
    }
  })

export type OnboardingValues = z.infer<typeof onboardingSchema>

export type StepId =
  'profil' | 'objectif' | 'activite' | 'rythme' | 'calories' | 'macros' | 'resume'

export interface StepDefinition {
  id: StepId
  title: string
  /** Champs validés avant de pouvoir avancer. */
  fields: readonly (keyof OnboardingValues)[]
}

/** Les 7 étapes de la spec 01 §2 et de la spec 06 §4. */
export const STEPS: readonly StepDefinition[] = [
  {
    id: 'profil',
    title: 'Profil',
    fields: ['birth_date', 'sex_for_calculation', 'height_cm', 'weight_kg'],
  },
  { id: 'objectif', title: 'Objectif', fields: ['goal_type', 'target_weight_kg'] },
  { id: 'activite', title: 'Activité', fields: ['activity_level'] },
  { id: 'rythme', title: 'Rythme', fields: ['goal_rate_kg_per_week'] },
  { id: 'calories', title: 'Calories', fields: ['daily_calories'] },
  { id: 'macros', title: 'Macros', fields: ['protein_g', 'carbs_g', 'fat_g'] },
  { id: 'resume', title: 'Résumé', fields: [] },
]

export const SEX_OPTIONS: readonly SelectOption[] = [
  { value: 'FEMALE', label: 'Femme' },
  { value: 'MALE', label: 'Homme' },
]

export const GOAL_OPTIONS: readonly CardOption<GoalType>[] = [
  { value: 'LOSS', label: 'Perdre du poids', description: 'Objectif calorique en déficit.' },
  {
    value: 'MAINTENANCE',
    label: 'Maintenir mon poids',
    description: 'Objectif calorique à l’équilibre.',
  },
  { value: 'GAIN', label: 'Prendre du poids', description: 'Objectif calorique en surplus.' },
]

export const ACTIVITY_OPTIONS: readonly CardOption<ActivityLevel>[] = [
  { value: 'SEDENTARY', label: 'Sédentaire', description: 'Peu ou pas d’activité physique.' },
  {
    value: 'LIGHTLY_ACTIVE',
    label: 'Légèrement actif',
    description: 'Activité légère 1 à 3 jours par semaine.',
  },
  {
    value: 'MODERATELY_ACTIVE',
    label: 'Modérément actif',
    description: 'Activité modérée 3 à 5 jours par semaine.',
  },
  {
    value: 'VERY_ACTIVE',
    label: 'Très actif',
    description: 'Activité soutenue 6 à 7 jours par semaine.',
  },
  {
    value: 'EXTREMELY_ACTIVE',
    label: 'Extrêmement actif',
    description: 'Activité intense quotidienne ou métier physique.',
  },
]

export const RATE_OPTIONS: readonly CardOption<string>[] = [
  { value: '0.25', label: '0,25 kg par semaine', description: 'Progressif et facile à tenir.' },
  { value: '0.50', label: '0,5 kg par semaine', description: 'Rythme couramment recommandé.' },
  { value: '0.75', label: '0,75 kg par semaine', description: 'Soutenu.' },
  { value: '1.00', label: '1 kg par semaine', description: 'Ambitieux, plus difficile à tenir.' },
]

export const SEX_LABELS: Record<SexForCalculation, string> = {
  FEMALE: 'Femme',
  MALE: 'Homme',
}

export const GOAL_LABELS: Record<GoalType, string> = {
  LOSS: 'Perte de poids',
  MAINTENANCE: 'Maintien du poids',
  GAIN: 'Prise de poids',
}

export const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  SEDENTARY: 'Sédentaire',
  LIGHTLY_ACTIVE: 'Légèrement actif',
  MODERATELY_ACTIVE: 'Modérément actif',
  VERY_ACTIVE: 'Très actif',
  EXTREMELY_ACTIVE: 'Extrêmement actif',
}

export const EMPTY_DRAFT: OnboardingValues = {
  birth_date: '',
  sex_for_calculation: 'FEMALE',
  height_cm: '',
  weight_kg: '',
  goal_type: 'MAINTENANCE',
  target_weight_kg: '',
  activity_level: 'MODERATELY_ACTIVE',
  goal_rate_kg_per_week: '',
  daily_calories: '',
  protein_g: '',
  carbs_g: '',
  fat_g: '',
}
