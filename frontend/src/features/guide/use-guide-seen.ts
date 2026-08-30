import { useSyncExternalStore } from 'react'

/**
 * Le guide a-t-il déjà été ouvert sur cet appareil ?
 *
 * Conservé dans le navigateur plutôt que sur le serveur : ce n'est pas une
 * donnée du compte mais un confort d'affichage, et le retrouver au premier
 * usage d'un nouvel appareil est plutôt souhaitable.
 *
 * Chaque accès est protégé : un navigateur en navigation privée, ou réglé pour
 * refuser le stockage, lève au lieu de renvoyer `null`. L'invitation
 * s'affiche alors à chaque visite — un défaut sans conséquence, contrairement
 * à une page blanche.
 */
const KEY = 'mfp.guide-seen'

const listeners = new Set<() => void>()

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function markGuideSeen(): void {
  try {
    window.localStorage.setItem(KEY, '1')
  } catch {
    // Rien à faire : l'invitation restera affichée.
  }
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** `true` tant que le guide n'a pas été ouvert sur cet appareil. */
export function useGuideUnseen(): boolean {
  return !useSyncExternalStore(subscribe, read, () => true)
}
