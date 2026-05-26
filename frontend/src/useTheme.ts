/**
 * useTheme — reads/writes the active theme.
 *
 * Sets `data-theme="light"|"dark"` on <html>.
 * CSS in index.css defines variables for both.
 * Persists to localStorage so it survives page refreshes.
 */

import { useState, useEffect } from 'react'

export type Theme = 'light' | 'dark'

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('anavi-theme') as Theme | null
    return saved ?? 'light'            // light is the default
  })

  useEffect(() => {
    apply(theme)
    localStorage.setItem('anavi-theme', theme)
  }, [theme])

  // Apply immediately on mount (avoids flash)
  useEffect(() => { apply(theme) }, [])

  const toggle = () => setTheme(t => (t === 'light' ? 'dark' : 'light'))
  return [theme, toggle]
}
