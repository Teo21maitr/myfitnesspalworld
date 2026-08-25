import { resetThrottleCounters } from './helpers'

/**
 * Remet à zéro les compteurs de limitation de débit avant le parcours.
 *
 * Le throttling reste actif — il est vérifié par les tests backend — mais
 * plusieurs exécutions successives du parcours partageraient sinon le même
 * compteur et déclencheraient une 429.
 */
export default function globalSetup(): void {
  resetThrottleCounters()
}
