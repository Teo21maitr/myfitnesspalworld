import { TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'

import { Label } from '@/components/ui/label'
import type { NotificationPreference } from '@/lib/api/types'
import { describeError } from '@/lib/query-client'

import { useSavePreferences } from './use-notifications'

type Channel = 'in_app_enabled' | 'email_enabled'

/**
 * Une case par canal et par type (spec 01 §24).
 *
 * La colonne push est **affichée désactivée**, avec sa raison : la PWA n'a pas
 * encore de service worker capable de la recevoir, et une case qui ne fait
 * rien est pire qu'une case grisée.
 */
export function PreferenceForm({ preferences }: { preferences: NotificationPreference[] }) {
  const save = useSavePreferences()

  const toggle = (row: NotificationPreference, channel: Channel) => {
    save.mutate([{ ...row, [channel]: !row[channel] }], {
      onSuccess: () => toast.success('Préférences enregistrées.'),
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Les trois colonnes de canaux se serraient à 375 px, au point que
          leurs en-têtes se touchaient. Largeur fixe et défilement horizontal
          plutôt qu'un rognage : le tableau reste lisible sur un téléphone. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[22rem] text-sm">
          <thead>
            <tr className="text-muted-foreground text-xs">
              <th scope="col" className="pb-2 pr-2 text-left font-medium">
                Événement
              </th>
              <th scope="col" className="w-16 pb-2 font-medium">
                Appli.
              </th>
              <th scope="col" className="w-16 pb-2 font-medium">
                Email
              </th>
              <th scope="col" className="w-16 pb-2 font-medium">
                Push
              </th>
            </tr>
          </thead>
          <tbody>
            {preferences.map((row) => (
              <tr key={row.event_type} className="border-t">
                <th scope="row" className="py-2 pr-2 text-left font-normal">
                  {row.event_label}
                </th>
                {(['in_app_enabled', 'email_enabled'] as Channel[]).map((channel) => (
                  <td key={channel} className="py-2 text-center">
                    <input
                      type="checkbox"
                      className="size-4"
                      aria-label={`${row.event_label} — ${channel === 'in_app_enabled' ? 'application' : 'email'}`}
                      checked={row[channel]}
                      disabled={save.isPending}
                      onChange={() => toggle(row, channel)}
                    />
                  </td>
                ))}
                <td className="py-2 text-center">
                  <input
                    type="checkbox"
                    className="size-4"
                    aria-label={`${row.event_label} — push`}
                    checked={false}
                    disabled
                    readOnly
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Label className="text-muted-foreground text-xs font-normal">
        Le canal push n’est pas encore disponible : l’application ne sait pas encore recevoir de
        notification quand elle est fermée.
      </Label>

      {save.isError && (
        <p role="alert" className="text-destructive flex items-start gap-2 text-sm">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {describeError(save.error)}
        </p>
      )}
    </div>
  )
}
