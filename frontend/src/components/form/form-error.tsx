import { TriangleAlert } from 'lucide-react'

/** Message d'erreur global d'un formulaire (erreur non liée à un champ). */
export function FormError({ message }: { message?: string }) {
  if (!message) return null

  return (
    <p
      role="alert"
      className="text-destructive bg-destructive/10 flex items-start gap-2 rounded-md p-3 text-sm"
    >
      <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {message}
    </p>
  )
}
