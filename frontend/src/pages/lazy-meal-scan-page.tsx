import { lazy, Suspense } from 'react'

/**
 * Enveloppe différée de Meal Scan.
 *
 * L'écran n'a pas de bibliothèque lourde derrière lui — contrairement au
 * scanner de codes-barres — mais il reste inutile de le télécharger à chaque
 * ouverture de l'application : la plupart des sessions n'analysent aucune
 * photo.
 *
 * Ce composant vit dans son propre fichier pour que le routeur n'exporte que
 * des routes : y mêler un composant casserait le rafraîchissement à chaud.
 */
const MealScanPage = lazy(() =>
  import('./meal-scan-page').then((module) => ({ default: module.MealScanPage })),
)

export function LazyMealScanPage() {
  return (
    <Suspense
      fallback={
        <div aria-busy="true" className="mx-auto w-full max-w-2xl">
          <div className="bg-muted h-64 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement de l’analyse photo…</span>
        </div>
      }
    >
      <MealScanPage />
    </Suspense>
  )
}
