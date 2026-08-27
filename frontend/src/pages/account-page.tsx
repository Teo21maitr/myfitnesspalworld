import { Share2, Target, TrendingUp, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ChangePasswordForm } from '@/features/account/change-password-form'
import { DeleteAccountSection } from '@/features/account/delete-account-section'
import { ProfileForm } from '@/features/account/profile-form'
import { SessionSection } from '@/features/account/session-section'
import { useMe } from '@/features/auth/use-auth'
import { HealthCard } from '@/features/health/health-card'

export function AccountPage() {
  const { data: user } = useMe()

  // La route est protégée par `RequireAuth` : l'utilisateur est toujours
  // résolu quand cette page est rendue.
  if (!user) return null

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mon compte</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Connecté en tant que <span className="font-medium">{user.username}</span>.
        </p>
      </div>

      {/* « Objectifs » n'a plus d'entrée dans la barre mobile depuis que
          « Progression » y a pris sa place : ces deux liens la gardent
          atteignable au doigt. */}
      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline" size="sm">
          <Link to="/objectifs">
            <Target aria-hidden="true" className="size-4" />
            Objectifs
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link to="/progression">
            <TrendingUp aria-hidden="true" className="size-4" />
            Progression
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link to="/amis">
            <Users aria-hidden="true" className="size-4" />
            Amis
          </Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link to="/partages">
            <Share2 aria-hidden="true" className="size-4" />
            Partages
          </Link>
        </Button>
      </div>

      <ProfileForm user={user} />
      <ChangePasswordForm />
      <SessionSection />
      {/* Diagnostic technique : il a quitté l'accueil, devenu le tableau de
          bord, mais reste utile pour savoir si le serveur répond. */}
      <HealthCard />
      <DeleteAccountSection user={user} />
    </div>
  )
}
