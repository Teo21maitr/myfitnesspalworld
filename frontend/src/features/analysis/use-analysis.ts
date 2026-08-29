import { useMutation, useQuery } from '@tanstack/react-query'

import {
  analysisQueryKey,
  downloadReport,
  fetchNutrientAnalysis,
  fetchReport,
  reportQueryKey,
  type ExportFormat,
} from './api'
import { reportFilename, saveBlob } from './download'

export function useNutrientAnalysis(nutrient: string, from: string, to: string) {
  return useQuery({
    queryKey: analysisQueryKey(nutrient, from, to),
    queryFn: () => fetchNutrientAnalysis(nutrient, from, to),
  })
}

export function useReport(from: string, to: string) {
  return useQuery({
    queryKey: reportQueryKey(from, to),
    queryFn: () => fetchReport(from, to),
  })
}

/**
 * Télécharge un export.
 *
 * Aucune invalidation : un export ne modifie rien, il lit.
 */
export function useReportExport(from: string, to: string) {
  return useMutation({
    mutationFn: async (format: ExportFormat) => {
      const blob = await downloadReport(format, from, to)
      saveBlob(blob, reportFilename(format, from, to))
      return format
    },
  })
}
