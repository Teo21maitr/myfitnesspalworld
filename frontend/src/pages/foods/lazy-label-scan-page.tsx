import { lazy, Suspense } from 'react'

/**
 * Enveloppe différée de la lecture d'étiquette.
 *
 * Elle embarque la prise de vue et le formulaire d'aliment : inutile de les
 * télécharger à chaque ouverture de l'application, la plupart des sessions ne
 * créant aucun aliment.
 */
const LabelScanPage = lazy(() =>
  import('./label-scan-page').then((module) => ({ default: module.LabelScanPage })),
)

export function LazyLabelScanPage() {
  return (
    <Suspense
      fallback={
        <div aria-busy="true" className="mx-auto w-full max-w-2xl">
          <div className="bg-muted h-64 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement de la lecture d’étiquette…</span>
        </div>
      }
    >
      <LabelScanPage />
    </Suspense>
  )
}
