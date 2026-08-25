import { useEffect, useState } from 'react'

/**
 * Retarde la propagation d'une valeur.
 *
 * Utilisé par la recherche d'aliments : la spec 11 §5 interdit d'interroger
 * une source à chaque frappe.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])

  return debounced
}
