import { MailCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function RegistrationSentPage() {
  return (
    <Card>
      <CardHeader>
        <MailCheck aria-hidden="true" className="text-primary size-8" />
        <CardTitle as="h1" className="text-xl">
          Demande envoyée
        </CardTitle>
        <CardDescription>Votre compte n’est pas encore actif.</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <p className="text-sm">
          Votre demande d’inscription a bien été envoyée. Un administrateur doit maintenant
          l’accepter avant que vous puissiez vous connecter.
        </p>
        <p className="text-muted-foreground text-sm">
          Si vous avez renseigné une adresse email, vous recevrez un message dès que votre compte
          sera activé.
        </p>

        <Button asChild variant="outline" className="self-start">
          <Link to="/connexion">Retour à la connexion</Link>
        </Button>
      </CardContent>
    </Card>
  )
}
