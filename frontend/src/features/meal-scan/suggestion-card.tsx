import { Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { SelectField } from '@/components/form/select-field'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { MealScanCandidate, MealScanSuggestion } from '@/lib/api/types'

import {
  estimatedEnergy,
  selectedCandidate,
  usableUnit,
  withCandidate,
  type ScanLine,
} from './lines'

function describeCandidate(name: string, brand: string, sourceLabel: string): string {
  return [name, brand, sourceLabel].filter(Boolean).join(' — ')
}

/**
 * Rappelle d'où vient le nombre affiché.
 *
 * Une énergie non renseignée se dit, elle ne se remplace pas par zéro
 * (spec 01 §8).
 */
function describeEnergy(candidate: MealScanCandidate, energy: number | null): string {
  if (candidate.nutrition.energy_kcal === null) {
    return 'Valeur énergétique non renseignée sur cette fiche'
  }
  if (energy === null) {
    const reference = Number(candidate.nutrition.energy_kcal).toLocaleString('fr-FR')
    return `${reference} kcal pour ${candidate.reference_amount} ${candidate.reference_unit}`
  }
  return `Environ ${Math.round(energy).toLocaleString('fr-FR')} kcal, d’après la fiche de l’aliment`
}

/**
 * Un aliment détecté, à confirmer ou à corriger.
 *
 * L'écran affiche la confiance du modèle, mais les valeurs nutritionnelles
 * proviennent toujours de la fiche choisie : le modèle a regardé une photo, il
 * n'a pas pesé l'assiette (spec 07 §1).
 */
export function SuggestionCard({
  suggestion,
  line,
  onChange,
  onRemove,
}: {
  suggestion: MealScanSuggestion
  line: ScanLine
  onChange: (line: ScanLine) => void
  onRemove: () => void
}) {
  const candidates = Array.isArray(suggestion.candidates) ? suggestion.candidates : []
  const candidate = selectedCandidate(suggestion, line)
  const units = candidate?.available_units ?? [suggestion.unit]
  const energy = estimatedEnergy(candidate, line)
  const confidence = Math.round(suggestion.confidence * 100)

  return (
    <li className="rounded-xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium">{suggestion.label}</p>
          <p className="text-muted-foreground text-xs">Confiance du modèle : {confidence} %</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Retirer ${suggestion.label}`}
          onClick={onRemove}
        >
          <Trash2 aria-hidden="true" className="size-4" />
        </Button>
      </div>

      {candidates.length === 0 ? (
        <div className="mt-3">
          <p className="text-muted-foreground text-sm">
            Aucun aliment de la base ne correspond à « {suggestion.label} ».
          </p>
          <Link
            to={`/aliments?q=${encodeURIComponent(suggestion.label)}`}
            className="text-primary mt-1 inline-block text-sm underline"
          >
            Chercher cet aliment
          </Link>
        </div>
      ) : (
        <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
          <SelectField
            label="Aliment"
            aria-label={`Aliment pour ${suggestion.label}`}
            value={line.foodId === null ? '' : String(line.foodId)}
            onChange={(event) =>
              onChange(
                withCandidate(
                  line,
                  suggestion,
                  event.target.value === '' ? null : Number(event.target.value),
                ),
              )
            }
            options={candidates.map((item) => ({
              value: String(item.id),
              label: describeCandidate(item.name, item.brand, item.source_label),
            }))}
          />

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`quantity-${line.key}`}>Quantité</Label>
            <Input
              id={`quantity-${line.key}`}
              inputMode="decimal"
              className="h-11 w-28"
              value={line.quantity}
              onChange={(event) => onChange({ ...line, quantity: event.target.value })}
            />
          </div>

          <SelectField
            label="Unité"
            aria-label={`Unité pour ${suggestion.label}`}
            className="w-32"
            value={usableUnit(candidate, line.unit)}
            onChange={(event) => onChange({ ...line, unit: event.target.value })}
            options={units.map((unit) => ({ value: unit, label: unit }))}
          />
        </div>
      )}

      {candidate && (
        <p className="text-muted-foreground mt-2 text-xs">{describeEnergy(candidate, energy)}</p>
      )}
    </li>
  )
}
