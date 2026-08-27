import type { MealScanCandidate, MealScanSuggestion } from '@/lib/api/types'

/**
 * Une ligne de l'écran de correction.
 *
 * Séparée du composant pour rester testable, et parce que le choix d'unité
 * porte une règle métier : changer d'aliment peut rendre l'unité courante
 * incalculable (spec 01 §9).
 */
export interface ScanLine {
  /** Identifie la ligne indépendamment de son contenu, qui change. */
  key: string
  foodId: number | null
  quantity: string
  unit: string
}

function candidateById(
  suggestion: MealScanSuggestion,
  foodId: number | null,
): MealScanCandidate | null {
  if (foodId === null) return null
  return suggestion.candidates.find((candidate) => candidate.id === foodId) ?? null
}

/**
 * Unité utilisable pour cet aliment.
 *
 * Même arbitrage que côté serveur : une unité que le backend refuserait ferait
 * échouer la confirmation en 400, pour un choix que l'utilisateur n'a pas fait.
 */
export function usableUnit(candidate: MealScanCandidate | null, unit: string): string {
  if (candidate === null) return unit
  const units = Array.isArray(candidate.available_units) ? candidate.available_units : []
  return units.includes(unit) ? unit : (units[0] ?? candidate.reference_unit)
}

/**
 * Quantité telle qu'on l'écrirait à la main.
 *
 * Le serveur renvoie des décimaux complets — « 150.000 » — parce que c'est la
 * forme exacte de la valeur. Dans un champ de saisie, c'est simplement moins
 * lisible que « 150 ».
 */
function tidyQuantity(raw: string): string {
  const value = Number(raw)
  return Number.isFinite(value) ? String(value) : raw
}

export function initialLines(suggestions: MealScanSuggestion[]): ScanLine[] {
  return suggestions.map((suggestion, index) => {
    const candidate = suggestion.candidates[0] ?? null
    return {
      key: `${index}-${suggestion.label}`,
      foodId: candidate?.id ?? null,
      quantity: tidyQuantity(suggestion.estimated_quantity),
      unit: usableUnit(candidate, suggestion.unit),
    }
  })
}

/** Change l'aliment retenu, en réajustant l'unité si elle ne convient plus. */
export function withCandidate(
  line: ScanLine,
  suggestion: MealScanSuggestion,
  foodId: number | null,
): ScanLine {
  const candidate = candidateById(suggestion, foodId)
  return { ...line, foodId, unit: usableUnit(candidate, line.unit) }
}

export function selectedCandidate(
  suggestion: MealScanSuggestion,
  line: ScanLine,
): MealScanCandidate | null {
  return candidateById(suggestion, line.foodId)
}

/**
 * Énergie approximative de la quantité saisie.
 *
 * Renvoie `null` dès que le facteur de conversion n'est pas connu du frontend
 * — une portion, par exemple. Le total qui compte est calculé par le serveur
 * à la confirmation : mieux vaut ne rien annoncer que d'annoncer à peu près
 * (spec 05 §12).
 */
export function estimatedEnergy(
  candidate: MealScanCandidate | null,
  line: ScanLine,
): number | null {
  if (candidate === null || candidate.nutrition.energy_kcal === null) return null
  if (line.unit !== candidate.reference_unit) return null

  const reference = Number(candidate.reference_amount)
  const quantity = Number(line.quantity.replace(',', '.'))
  if (!Number.isFinite(quantity) || !(reference > 0)) return null

  return (Number(candidate.nutrition.energy_kcal) * quantity) / reference
}

/** Lignes réellement journalisables : celles qui portent un aliment. */
export function loggableLines(lines: ScanLine[]): ScanLine[] {
  return lines.filter((line) => line.foodId !== null && Number(line.quantity) > 0)
}
