import {
  Apple,
  BookOpen,
  ChefHat,
  ScanBarcode,
  Target,
  TrendingUp,
  TriangleAlert,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { today } from '@/features/diary/dates'
import { useDashboard } from '@/features/diary/use-diary'
import { NutrientValue } from '@/features/foods/nutrient-value'
import type { Dashboard } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

/** Macronutriments suivis au quotidien (spec 06 §5). */
const MACROS = [
  { key: 'protein_g', goal: 'protein_g', label: 'Protéines' },
  { key: 'carbohydrates_g', goal: 'carbs_g', label: 'Glucides' },
  { key: 'fat_g', goal: 'fat_g', label: 'Lipides' },
] as const

const SHORTCUTS = [
  { to: '/aliments', label: 'Ajouter un aliment', Icon: Apple },
  { to: '/scanner', label: 'Scanner', Icon: ScanBarcode },
  { to: '/ajout-rapide', label: 'Ajout rapide', Icon: Zap },
  { to: '/recettes', label: 'Recettes', Icon: ChefHat },
]

function CaloriesCard({ day }: { day: Dashboard }) {
  const remaining = day.remaining?.daily_calories ?? null

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
        <CardTitle as="h2" className="text-base">
          Calories
        </CardTitle>
        {/* « Objectifs » a cédé sa place à « Progression » dans la barre
            mobile : ce lien reste sa porte d'entrée, y compris lorsqu'un
            objectif est déjà défini. */}
        <Button asChild variant="ghost" size="sm">
          <Link to="/objectifs">
            <Target aria-hidden="true" className="size-4" />
            Objectifs
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <p className="text-3xl font-semibold">
          <NutrientValue value={day.totals.energy_kcal} unit="kcal" />
        </p>

        {day.goals ? (
          <p className="text-muted-foreground text-sm">
            sur <NutrientValue value={day.goals.daily_calories} unit="kcal" /> ·{' '}
            <span className="font-medium">
              <NutrientValue value={remaining} unit="kcal" /> restantes
            </span>
          </p>
        ) : (
          <p className="text-muted-foreground text-sm">
            Aucun objectif défini.{' '}
            <Link to="/objectifs" className="underline">
              En définir un
            </Link>
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function MacrosCard({ day }: { day: Dashboard }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle as="h2" className="text-base">
          Macronutriments
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-3 gap-4">
          {MACROS.map(({ key, goal, label }) => (
            <div key={key} className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">{label}</dt>
              <dd className="text-lg font-semibold">
                <NutrientValue value={day.totals[key]} unit="g" />
              </dd>
              {day.goals && (
                <p className="text-muted-foreground text-xs">
                  sur <NutrientValue value={day.goals[goal]} unit="g" />
                </p>
              )}
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function WeightCard({ weight }: { weight: Dashboard['weight'] }) {
  const change = weight.change_kg === null ? null : Number(weight.change_kg)

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
        <CardTitle as="h2" className="text-base">
          Poids
        </CardTitle>
        <Button asChild variant="ghost" size="sm">
          <Link to="/progression">
            <TrendingUp aria-hidden="true" className="size-4" />
            Progression
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        {weight.latest_kg === null ? (
          <p className="text-muted-foreground text-sm">
            Aucune pesée enregistrée.{' '}
            <Link to="/progression" className="underline">
              Enregistrer une pesée
            </Link>
          </p>
        ) : (
          <>
            <p className="text-3xl font-semibold">
              <NutrientValue value={weight.latest_kg} unit="kg" />
            </p>

            {change !== null && change !== 0 && (
              <p className="text-muted-foreground text-sm">
                {change > 0 ? '+' : '−'}
                {Math.abs(change).toLocaleString('fr-FR')} kg depuis le début
              </p>
            )}

            {weight.progress_percent !== null && (
              <p className="text-muted-foreground text-sm">
                {Number(weight.progress_percent).toLocaleString('fr-FR')} % du chemin vers{' '}
                <NutrientValue value={weight.target_kg} unit="kg" />
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function MealsCard({ day }: { day: Dashboard }) {
  const meals = Array.isArray(day.meals) ? day.meals : []

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
        <CardTitle as="h2" className="text-base">
          Repas du jour
        </CardTitle>
        <Button asChild variant="ghost" size="sm">
          <Link to="/journal">
            <BookOpen aria-hidden="true" className="size-4" />
            Journal
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col">
          {meals.map((section) => (
            <div
              key={section.meal_type.id}
              className="flex items-baseline justify-between gap-4 border-b py-1.5 last:border-b-0"
            >
              <dt className="text-sm">{section.meal_type.name}</dt>
              <dd className="text-sm font-medium">
                <NutrientValue value={section.totals.energy_kcal} unit="kcal" />
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

export function HomePage() {
  const date = today()
  const { data: day, error, isPending } = useDashboard(date)

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Aujourd’hui</h1>
        <p className="text-muted-foreground mt-1 text-sm first-letter:uppercase">
          {new Date(`${date}T12:00:00`).toLocaleDateString('fr-FR', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
          })}
        </p>
      </div>

      {isPending && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <div className="bg-muted h-32 animate-pulse rounded-xl" />
          <div className="bg-muted h-28 animate-pulse rounded-xl" />
          <span className="sr-only">Chargement du tableau de bord…</span>
        </div>
      )}

      {error && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(error)}
        </p>
      )}

      {day && (
        <>
          <CaloriesCard day={day} />
          <MacrosCard day={day} />
          <MealsCard day={day} />
          <WeightCard weight={day.weight} />

          <Card>
            <CardHeader>
              <CardTitle as="h2" className="text-base">
                Ajouter
              </CardTitle>
              <CardDescription>Les trois façons les plus rapides d’enregistrer.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {SHORTCUTS.map(({ to, label, Icon }) => (
                <Button key={to} asChild variant="outline" size="sm">
                  <Link to={to}>
                    <Icon aria-hidden="true" className="size-4" />
                    {label}
                  </Link>
                </Button>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
