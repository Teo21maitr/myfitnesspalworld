import { Monitor, Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useThemePreference } from '@/features/settings/use-settings'
import type { ThemeMode } from '@/lib/api/types'
import { cn } from '@/lib/utils'

const OPTIONS: { value: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Thème clair', Icon: Sun },
  { value: 'dark', label: 'Thème sombre', Icon: Moon },
  { value: 'system', label: 'Thème système', Icon: Monitor },
]

export function ThemeToggle() {
  const { theme, changeTheme } = useThemePreference()

  return (
    <div
      role="group"
      aria-label="Choix du thème"
      className="bg-secondary flex items-center gap-1 rounded-lg p-1"
    >
      {OPTIONS.map(({ value, label, Icon }) => (
        <Button
          key={value}
          type="button"
          size="icon"
          variant="ghost"
          aria-label={label}
          aria-pressed={theme === value}
          onClick={() => changeTheme(value)}
          className={cn('size-9', theme === value && 'bg-background shadow-xs')}
        >
          <Icon aria-hidden="true" />
        </Button>
      ))}
    </div>
  )
}
