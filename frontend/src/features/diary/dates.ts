/** Utilitaires de date du journal, en heure locale. */

/** Date du jour au format attendu par l'API (AAAA-MM-JJ). */
export function today(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

/**
 * Décale une date ISO d'un nombre de jours.
 *
 * Le passage par midi évite qu'un changement d'heure ne fasse basculer la
 * date d'un jour.
 */
export function shift(date: string, days: number): string {
  const value = new Date(`${date}T12:00:00`)
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}

export function formatDate(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}
