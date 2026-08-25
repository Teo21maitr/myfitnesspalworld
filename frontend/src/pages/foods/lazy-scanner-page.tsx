import { lazy, Suspense } from 'react'

/**
 * Enveloppe différée du scanner.
 *
 * Sa bibliothèque de secours de lecture de codes-barres pèse plusieurs
 * centaines de kilo-octets : elle n'a rien à faire dans le bundle que
 * télécharge quelqu'un venu simplement consulter son journal.
 *
 * Ce composant vit dans son propre fichier pour que le routeur n'exporte que
 * des routes : y mêler un composant casserait le rafraîchissement à chaud.
 */
const ScannerPage = lazy(() =>
  import('./scanner-page').then((module) => ({ default: module.ScannerPage })),
)

export function LazyScannerPage() {
  return (
    <Suspense
      fallback={
        <div aria-busy="true" className="mx-auto w-full max-w-2xl">
          <div className="bg-muted h-64 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement du scanner…</span>
        </div>
      }
    >
      <ScannerPage />
    </Suspense>
  )
}
