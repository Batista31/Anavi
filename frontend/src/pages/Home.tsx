import { useNavigate } from 'react-router-dom'
import { useTheme } from '../useTheme'
import ThemeToggle from '../components/ThemeToggle'
import { useScrollReveal } from '../hooks/useScrollReveal'

const FEATURES = [
  {
    index: '01',
    title: 'Photographic Reconstruction',
    body: 'Upload overlapping photographs of any space. ANAVI stitches them into a unified top-view map using computer vision, then generates a 3D height surface from edge detection.',
  },
  {
    index: '02',
    title: 'Multi-Algorithm Pathfinding',
    body: 'Three algorithms, all written from scratch: A* with an octile heuristic, Dijkstra for uniform cost traversal, and RRT for probabilistic exploration. Select and compare at runtime.',
  },
  {
    index: '03',
    title: 'Sensor-Free Robot Navigation',
    body: 'The computed path is exported as a structured waypoint file. Feed it directly to any pre-programmed ground robot — no onboard sensors, no real-time compute required.',
  },
]

export default function Home() {
  const nav = useNavigate()
  const [theme, toggleTheme] = useTheme()
  useScrollReveal()

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--color-base)', color: 'var(--color-cream)' }}
    >
      {/* ── Header — dark green in both themes ── */}
      <header
        className="flex items-center justify-between px-10 py-5"
        style={{ background: 'var(--color-forest)', borderBottom: '1px solid var(--color-forest-lt)' }}
      >
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: '1.5rem', fontWeight: 500,
          letterSpacing: '0.12em',
          color: 'var(--color-wordmark)',       /* warm beige on dark green */
        }}>
          ANAVI
        </div>

        <nav className="flex items-center gap-6">
          {['About', 'Docs'].map(l => (
            <span
              key={l}
              className="cursor-pointer nav-link"
              style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', letterSpacing: '0.18em', color: 'var(--color-forest-text)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-cream)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-forest-text)')}
            >
              {l.toUpperCase()}
            </span>
          ))}
          <ThemeToggle theme={theme} toggle={toggleTheme} />
          <button
            onClick={() => nav('/upload')}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              letterSpacing: '0.18em',
              padding: '0.55rem 1.4rem',
              background: 'var(--color-gold)',
              color: 'var(--color-forest)',    /* green text on gold */
              border: 'none',
              cursor: 'pointer',
              fontWeight: 400,
            }}
            onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold-lt)')}
            onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold)')}
          >
            OPEN MAP
          </button>
        </nav>
      </header>

      {/* ── Hero ── */}
      <section
        className="dot-grid flex-1 flex flex-col justify-center px-10 py-28"
        style={{ maxWidth: '960px', margin: '0 auto', width: '100%' }}
      >
        <div
          className="reveal"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.28em',
            color: 'var(--color-gold-dk)',
            marginBottom: '1.5rem',
          }}
        >
          AUTONOMOUS NAVIGATION SYSTEM · v2.0
        </div>

        <h1
          className="reveal reveal-d1"
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(4rem, 10vw, 7rem)',
            fontWeight: 500,
            letterSpacing: '-0.01em',
            lineHeight: 0.95,
            color: 'var(--color-cream)',
            marginBottom: '2rem',
          }}
        >
          Terrain-aware<br />
          <em style={{ color: 'var(--color-gold-dk)', fontStyle: 'italic' }}>path planning</em><br />
          from photographs.
        </h1>

        <p
          className="reveal reveal-d2"
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '1rem',
            fontWeight: 300,
            lineHeight: 1.75,
            color: 'var(--color-muted)',
            maxWidth: '520px',
            marginBottom: '3rem',
          }}
        >
          Upload photos of any layout. ANAVI reconstructs a navigable map,
          lets you mark two points, and computes an optimal path — ready
          for a ground robot with no onboard sensors.
        </p>

        <div className="flex items-center gap-5 reveal reveal-d3">
          <button
            onClick={() => nav('/upload')}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.72rem',
              letterSpacing: '0.18em',
              padding: '0.8rem 2.2rem',
              background: 'var(--color-gold)',
              color: 'var(--color-forest)',
              border: 'none',
              cursor: 'pointer',
            }}
            onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold-lt)')}
            onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold)')}
          >
            UPLOAD PHOTOS
          </button>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.72rem',
              letterSpacing: '0.18em',
              color: 'var(--color-faint)',
            }}
          >
            A* · DIJKSTRA · RRT
          </span>
        </div>
      </section>

      {/* ── Curved wave divider ── */}
      <div style={{ position: 'relative', lineHeight: 0, marginTop: '2rem' }}>
        <svg
          viewBox="0 0 1440 110"
          preserveAspectRatio="none"
          style={{ display: 'block', width: '100%', height: '110px' }}
          aria-hidden="true"
        >
          <path
            d="M0,110 L0,80 C200,110 400,20 720,20 C1040,20 1240,110 1440,80 L1440,110 Z"
            fill="var(--wave-top)"
          />
        </svg>
      </div>

      {/* ── Features ── */}
      <section
        style={{ background: 'var(--color-surface)', width: '100%', padding: '0 0 5rem' }}
      >
      <div style={{ maxWidth: '960px', margin: '0 auto', padding: '0 2.5rem' }}>
        <div
          className="reveal"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.28em',
            color: 'var(--color-muted)',
            marginBottom: '3rem',
            paddingTop: '3rem',
          }}
        >
          CAPABILITIES
        </div>

        <div className="flex flex-col" style={{ gap: 0 }}>
          {FEATURES.map((f, i) => (
            <div
              key={f.index}
              className={`flex gap-10 py-8 reveal reveal-d${i + 1}`}
              style={{
                borderTop: i === 0 ? '1px solid var(--color-border2)' : 'none',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.65rem',
                  color: 'var(--color-index)',
                  letterSpacing: '0.1em',
                  paddingTop: '0.3rem',
                  minWidth: '2rem',
                }}
              >
                {f.index}
              </span>
              <div>
                <h3
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: '1.35rem',
                    fontWeight: 500,
                    color: 'var(--color-cream)',
                    marginBottom: '0.6rem',
                    letterSpacing: '0.01em',
                  }}
                >
                  {f.title}
                </h3>
                <p
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '0.875rem',
                    fontWeight: 300,
                    lineHeight: 1.75,
                    color: 'var(--color-muted)',
                    maxWidth: '560px',
                  }}
                >
                  {f.body}
                </p>
              </div>
            </div>
          ))}
        </div>
        </div> {/* inner max-width wrapper */}
      </section>

      {/* ── Reverse wave into footer ── */}
      <div style={{ lineHeight: 0, background: 'var(--wave-top)' }}>
        <svg
          viewBox="0 0 1440 90"
          preserveAspectRatio="none"
          style={{ display: 'block', width: '100%', height: '90px' }}
          aria-hidden="true"
        >
          <path
            d="M0,0 C200,0 500,90 720,90 C940,90 1240,0 1440,0 L1440,90 L0,90 Z"
            fill="var(--wave-footer)"
          />
        </svg>
      </div>

      {/* ── Footer — dark green ── */}
      <footer
        className="flex items-center justify-between px-10 py-6"
        style={{ background: 'var(--wave-footer)', marginTop: 0 }}
      >
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', letterSpacing: '0.18em', color: 'var(--color-forest-faint)' }}>
          ANAVI · AUTONOMOUS NAVIGATION · 2025
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', letterSpacing: '0.18em', color: 'var(--color-forest-faint)' }}>
          RVCE
        </span>
      </footer>
    </div>
  )
}
