import { WifiOff } from 'lucide-react'

import { useOnlineStatus } from '@/hooks/use-online-status'

export function OfflineBanner() {
  const isOnline = useOnlineStatus()

  if (isOnline) return null

  return (
    <div
      role="status"
      className="bg-warning text-warning-foreground flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium"
    >
      <WifiOff aria-hidden="true" className="size-4" />
      <span>Hors connexion — la consultation reste possible, pas la modification.</span>
    </div>
  )
}
