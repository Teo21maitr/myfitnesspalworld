import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

/**
 * Filet de sécurité pour les erreurs de rendu.
 *
 * Aucune erreur n'est masquée silencieusement (spec 10 §12) : l'utilisateur
 * voit un message clair et le détail technique reste dans la console.
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Erreur de rendu non gérée', error, info.componentStack)
  }

  override render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <div role="alert" className="flex flex-col items-start gap-4 p-6">
        <h1 className="text-xl font-semibold">Une erreur est survenue</h1>
        <p className="text-muted-foreground text-sm">
          L’application n’a pas pu afficher cette page.
        </p>
        <Button type="button" onClick={() => window.location.reload()}>
          Recharger
        </Button>
      </div>
    )
  }
}
