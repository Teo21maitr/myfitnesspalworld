import { api } from '@/lib/api/client'
import type { NutrientAnalysis, PeriodReport } from '@/lib/api/types'

export const analysisQueryKey = (nutrient: string, from: string, to: string) =>
  ['analysis', 'food', nutrient, from, to] as const

export const reportQueryKey = (from: string, to: string) =>
  ['analysis', 'report', from, to] as const

/** D'où vient un nutriment sur la période (spec 04 §18). */
export const fetchNutrientAnalysis = (nutrient: string, from: string, to: string) =>
  api.get<NutrientAnalysis>('/analysis/food/', { params: { nutrient, from, to } })

/** Résumé d'une période : moyennes, objectifs, poids et top aliments. */
export const fetchReport = (from: string, to: string) =>
  api.get<PeriodReport>('/reports/summary/', { params: { from, to } })

/** Résumé de la semaine commençant à `from` (spec 01 §22). */
export const fetchWeekly = (from: string) =>
  api.get<PeriodReport>('/analysis/weekly/', { params: { from } })

export type ExportFormat = 'csv' | 'pdf'

/**
 * Télécharge un export de la période.
 *
 * Le fichier arrive en `Blob` : le lire comme du texte corromprait le PDF.
 */
export const downloadReport = (format: ExportFormat, from: string, to: string) =>
  api.download(`/reports/${format}/`, { from, to })
