import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-start gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Page introuvable</h1>
      <p className="text-muted-foreground text-sm">
        Cette adresse ne correspond à aucune page de l’application.
      </p>
      <Button asChild variant="outline">
        <Link to="/">Retour à l’accueil</Link>
      </Button>
    </div>
  )
}
