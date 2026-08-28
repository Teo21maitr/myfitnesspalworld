import { useMutation } from '@tanstack/react-query'

import { useAsyncTask } from '@/features/tasks/use-task'
import type { MealScanResult } from '@/lib/api/types'

import { startMealScan } from './api'

export { isRunning } from '@/features/tasks/use-task'
export { useAIStatus } from '@/features/ai/status'

export function useStartMealScan() {
  return useMutation({ mutationFn: (images: File[]) => startMealScan(images) })
}

/** Suit l'analyse d'une photo de repas. */
export function useMealScanTask(taskId: string | null) {
  return useAsyncTask<MealScanResult>(taskId)
}
