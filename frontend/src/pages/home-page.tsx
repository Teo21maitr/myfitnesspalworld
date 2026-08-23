import { HealthCard } from '@/features/health/health-card'

export function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">MyFitnessPalworld</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Socle technique en place. Les fonctionnalités de suivi alimentaire arrivent ensuite.
        </p>
      </div>

      <HealthCard />
    </div>
  )
}
