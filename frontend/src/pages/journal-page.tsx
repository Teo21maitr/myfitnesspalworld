import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/** Page volontairement vide : le journal sera implémenté après le socle. */
export function JournalPage() {
  return (
    <div className="mx-auto w-full max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Journal</CardTitle>
          <CardDescription>Bientôt disponible</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Le journal alimentaire n’est pas encore implémenté. Cette page confirme que le routage
            fonctionne.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
