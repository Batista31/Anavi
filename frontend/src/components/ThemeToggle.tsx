import type { Theme } from '../useTheme'

interface Props {
  theme: Theme
  toggle: () => void
}

/**
 * Minimal theme toggle — a small pill that shows the current mode
 * and switches on click. Styled to match the active theme.
 */
export default function ThemeToggle({ theme, toggle }: Props) {
  const isDark = theme === 'dark'

  return (
    <button
      onClick={toggle}
      title={`Switch to ${isDark ? 'light' : 'dark'} theme`}
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.6rem',
        letterSpacing: '0.2em',
        padding: '0.3rem 0.75rem',
        background: 'transparent',
        color: 'var(--color-muted)',
        border: '1px solid var(--color-border2)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '0.45rem',
        transition: 'color 0.15s, border-color 0.15s',
        userSelect: 'none',
      }}
      onMouseEnter={e => {
        const b = e.currentTarget as HTMLButtonElement
        b.style.color = 'var(--color-cream)'
        b.style.borderColor = 'var(--color-border3)'
      }}
      onMouseLeave={e => {
        const b = e.currentTarget as HTMLButtonElement
        b.style.color = 'var(--color-muted)'
        b.style.borderColor = 'var(--color-border2)'
      }}
    >
      {/* Small indicator dot */}
      <span style={{
        width: '6px', height: '6px',
        borderRadius: '50%',
        background: isDark ? 'var(--color-gold)' : 'var(--color-cream)',
        display: 'inline-block',
        flexShrink: 0,
      }} />
      {isDark ? 'NIGHT' : 'DAY'}
    </button>
  )
}
