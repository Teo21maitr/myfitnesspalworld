import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useMe } from './use-auth'

/** Écran d'attente affiché tant que l'authentification n'est pas résolue. */
function AuthLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-dvh flex-col items-center justify-center gap-3"
    >
      <div className="border-muted border-t-primary size-8 animate-spin rounded-full border-4" />
      <span className="text-muted-foreground text-sm">Chargement de votre session…</span>
    </div>
  )
}

/**
 * Garde de route privée.
 *
 * Rien de privé n'est rendu avant que `/auth/me/` ait répondu : aucun flash de
 * contenu authentifié n'est possible (spec 06 §11).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending, isError } = useMe()
  const location = useLocation()

  if (isPending) {
    return <AuthLoading />
  }

  if (isError || !user) {
    // La route demandée est mémorisée pour y revenir après connexion.
    return <Navigate to="/connexion" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}

/** Empêche un utilisateur déjà connecté de revenir sur les écrans publics. */
export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useMe()

  if (isPending) {
    return <AuthLoading />
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

/**
 * Garde d'onboarding.
 *
 * Un compte actif dont l'onboarding n'est pas terminé ne peut pas atteindre
 * l'application : il est renvoyé vers le parcours de configuration
 * (spec 02 §1, étape 10).
 */
export function RequireOnboarding({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useMe()

  if (isPending) {
    return <AuthLoading />
  }

  if (user && !user.onboarding_completed) {
    return <Navigate to="/onboarding" replace />
  }

  return <>{children}</>
}

/** Inverse : l'onboarding terminé, le parcours n'a plus lieu d'être. */
export function RedirectIfOnboarded({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useMe()

  if (isPending) {
    return <AuthLoading />
  }

  if (user?.onboarding_completed) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
