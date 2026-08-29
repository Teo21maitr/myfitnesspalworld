import { lazy, Suspense } from 'react'

/**
 * Enveloppes différées de la planification.
 *
 * Les deux écrans embarquent le formulaire de contraintes et l'affichage des
 * journées : inutile de les télécharger à chaque ouverture de l'application.
 */
const PlannerPage = lazy(() =>
  import('./planner-page').then((module) => ({ default: module.PlannerPage })),
)

const PlanPage = lazy(() => import('./plan-page').then((module) => ({ default: module.PlanPage })))

function Placeholder({ label }: { label: string }) {
  return (
    <div aria-busy="true" className="mx-auto w-full max-w-2xl">
      <div className="bg-muted h-64 animate-pulse rounded-xl" />
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function LazyPlannerPage() {
  return (
    <Suspense fallback={<Placeholder label="Chargement de la planification…" />}>
      <PlannerPage />
    </Suspense>
  )
}

export function LazyPlanPage() {
  return (
    <Suspense fallback={<Placeholder label="Chargement de la planification…" />}>
      <PlanPage />
    </Suspense>
  )
}
