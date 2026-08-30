import { Link } from 'react-router-dom'

import { NAV_SECTIONS } from '@/components/layout/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { GUIDE_DESCRIPTIONS, GUIDE_STEPS } from '@/features/guide/guide-content'
import { markGuideSeen } from '@/features/guide/use-guide-seen'
import { useEffect } from 'react'

/**
 * Guide d'utilisation (spec 06 §4).
 *
 * La page se construit à partir de `NAV_SECTIONS` : elle porte les mêmes
 * icônes et les mêmes libellés que le menu, si bien qu'un lecteur reconnaît
 * ensuite ce qu'il a lu. C'est le repère qu'apporteraient des captures d'écran,
 * sans leur défaut — une capture vieillit à la première retouche d'interface,
 * et personne ne s'en aperçoit.
 *
 * Chaque nom est un lien : le guide sert aussi de sommaire.
 */
export function GuidePage() {
  // Vu une fois, l'invitation de l'accueil disparaît.
  useEffect(markGuideSeen, [])

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Guide</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Ce que fait l’application, en quelques lignes par écran.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle as="h2">Par où commencer</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-col gap-4">
            {GUIDE_STEPS.map((step, index) => (
              <li key={step.to} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="bg-primary/10 text-primary flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
                >
                  {index + 1}
                </span>
                <div>
                  <Link to={step.to} className="font-medium underline-offset-4 hover:underline">
                    {step.title}
                  </Link>
                  <p className="text-muted-foreground mt-0.5 text-sm">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {NAV_SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle as="h2">{section.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-4">
              {section.items.map(({ to, label, Icon }) => (
                <li key={to} className="flex gap-3">
                  <Icon
                    aria-hidden="true"
                    className="text-muted-foreground mt-0.5 size-5 shrink-0"
                  />
                  <div>
                    <Link to={to} className="font-medium underline-offset-4 hover:underline">
                      {label}
                    </Link>
                    <p className="text-muted-foreground mt-0.5 text-sm">{GUIDE_DESCRIPTIONS[to]}</p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}

      <p className="text-muted-foreground text-sm">
        Tes données sont privées par défaut : rien n’est visible par quelqu’un d’autre tant que tu
        ne l’as pas partagé toi-même.
      </p>
    </div>
  )
}
