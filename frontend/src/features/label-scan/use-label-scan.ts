import { useMutation } from '@tanstack/react-query'

import { useAsyncTask } from '@/features/tasks/use-task'
import type { LabelScanResult } from '@/lib/api/types'

import { startLabelScan } from './api'

export function useStartLabelScan() {
  return useMutation({ mutationFn: (images: File[]) => startLabelScan(images) })
}

/** Suit la lecture d'une étiquette. */
export function useLabelScanTask(taskId: string | null) {
  return useAsyncTask<LabelScanResult>(taskId)
}
