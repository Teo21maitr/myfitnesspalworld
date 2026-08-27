import type { BodyMeasurementEntry } from '@/lib/api/types'

/** Mesures facultatives, dans l'ordre de la spec 01 §19. */
export const MEASUREMENT_FIELDS = [
  { key: 'waist_cm', label: 'Tour de taille', unit: 'cm' },
  { key: 'hips_cm', label: 'Tour de hanches', unit: 'cm' },
  { key: 'chest_cm', label: 'Tour de poitrine', unit: 'cm' },
  { key: 'arm_cm', label: 'Tour de bras', unit: 'cm' },
  { key: 'thigh_cm', label: 'Tour de cuisse', unit: 'cm' },
  { key: 'body_fat_percent', label: 'Masse grasse', unit: '%' },
] as const

export type MeasurementKey = (typeof MEASUREMENT_FIELDS)[number]['key']

export type MeasurementDraft = Record<MeasurementKey, string>

export const EMPTY_DRAFT: MeasurementDraft = {
  waist_cm: '',
  hips_cm: '',
  chest_cm: '',
  arm_cm: '',
  thigh_cm: '',
  body_fat_percent: '',
}

/** Reprend les mesures déjà relevées, pour éditer la journée plutôt que l'écraser. */
export function draftFrom(entry: BodyMeasurementEntry | undefined): MeasurementDraft {
  if (!entry) return EMPTY_DRAFT

  return MEASUREMENT_FIELDS.reduce((draft, field) => {
    const value = entry[field.key]
    return { ...draft, [field.key]: value === null ? '' : String(Number(value)) }
  }, EMPTY_DRAFT)
}
