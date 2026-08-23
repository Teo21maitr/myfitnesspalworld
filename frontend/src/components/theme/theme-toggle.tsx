import { Monitor, Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import type { Theme } from './theme-context'
import { useTheme } from './use-theme'

const OPTIONS: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Thème clair', Icon: Sun },
  { value: 'dark', label: 'Thème sombre', Icon: Moon },
  { value: 'system', label: 'Thème système', Icon: Monitor },
]

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

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
          onClick={() => setTheme(value)}
          className={cn('size-9', theme === value && 'bg-background shadow-xs')}
        >
          <Icon aria-hidden="true" />
        </Button>
      ))}
    </div>
  )
}
