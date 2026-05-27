import React, { useEffect, useState } from 'react'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { useNavigate } from 'react-router-dom'
import type { ProcessResponse, AiAnalysis, ImageClassification } from '../api'
import type { Waypoint, Algorithm } from '../types'
import MeshViewer from '../components/MeshViewer'
import { useTheme } from '../useTheme'
import ThemeToggle from '../components/ThemeToggle'

export default function Viewer() {
  const nav = useNavigate()
  const [session, setSession] = useState<ProcessResponse | null>(null)

  const [start, setStart] = useState<Waypoint | null>(null)
  const [goal, setGoal] = useState<Waypoint | null>(null)
  const [placing, setPlacing] = useState<'start' | 'goal' | null>(null)

  const [algorithm, setAlgorithm] = useState<Algorithm>('astar')
  const [path, setPath] = useState<[number, number][] | null>(null)
  const [computing, setComputing] = useState(false)
  const [noPath, setNoPath] = useState(false)

  useEffect(() => {
    const raw = sessionStorage.getItem('anavi_session')
    if (!raw) { nav('/upload'); return }
    setSession(JSON.parse(raw))
  }, [])

  const handleMeshClick = (row: number, col: number) => {
    if (placing === 'start') {
      setStart({ row, col })
      setPlacing('goal')
      setPath(null)
      setNoPath(false)
    } else if (placing === 'goal') {
      setGoal({ row, col })
      setPlacing(null)
    }
  }

  const compute = async () => {
    if (!session || !start || !goal) return
    setComputing(true)
    setNoPath(false)
    setPath(null)
    try {
      const { pathfind } = await import('../api')
      const res = await pathfind(
        session.session_id,
        [start.row, start.col],
        [goal.row, goal.col],
        algorithm,
      )
      if (res.path) setPath(res.path)
      else setNoPath(true)
    } finally {
      setComputing(false)
    }
  }

  const reset = () => {
    setStart(null)
    setGoal(null)
    setPath(null)
    setPlacing(null)
    setNoPath(false)
  }

  const [theme, toggleTheme] = useTheme()
  useScrollReveal()

  if (!session) return null

  const mono = { fontFamily: 'var(--font-mono)' } as const
  const algoMeta: Record<Algorithm, string> = {
    astar:    'Optimal · octile heuristic',
    dijkstra: 'Optimal · uniform cost',
    rrt:      'Non-optimal · random tree',
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--color-base)', color: 'var(--color-cream)' }}>

      {/* ── Top bar ── */}
      <header
        className="flex items-center justify-between px-8 py-4 shrink-0"
        style={{ background: 'var(--color-forest)', borderBottom: '1px solid var(--color-forest-lt)' }}
      >
        <button
          onClick={() => nav('/')}
          style={{ ...mono, fontSize: '0.68rem', letterSpacing: '0.2em', color: 'var(--color-forest-text)', background: 'none', border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-cream)')}
          onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-forest-text)')}
        >← ANAVI</button>

        <div className="flex items-center gap-4">
          <span style={{ ...mono, fontSize: '0.62rem', letterSpacing: '0.22em', color: 'var(--color-forest-faint)' }}>
            SES·{session.session_id.toUpperCase()} &nbsp;·&nbsp; {session.grid_size}×{session.grid_size} GRID
          </span>
          <ThemeToggle theme={theme} toggle={toggleTheme} />
        </div>

        <button
          onClick={() => nav('/upload')}
          style={{ ...mono, fontSize: '0.68rem', letterSpacing: '0.2em', color: 'var(--color-forest-text)', background: 'none', border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-cream)')}
          onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-forest-text)')}
        >NEW MAP →</button>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* ── 3D Canvas ── */}
        <div className="flex-1 relative">
          <MeshViewer
            session={session} start={start} goal={goal} path={path}
            onMeshClick={handleMeshClick} isPlacing={placing !== null}
          />

          {/* Placement hint */}
          {placing && (
            <div
              className="absolute top-5 left-1/2 -translate-x-1/2 pointer-events-none"
              style={{
                ...mono, fontSize: '0.65rem', letterSpacing: '0.24em',
                color: 'var(--color-gold)',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-gold-dk)',
                padding: '0.5rem 1.4rem',
              }}
            >
              CLICK TO SET {placing.toUpperCase()} POINT
            </div>
          )}
        </div>

        {/* ── Control Panel ── */}
        <aside
          className="flex flex-col shrink-0 overflow-y-auto reveal reveal-d1"
          style={{
            width: '280px',
            background: 'var(--color-surface)',
            borderLeft: '1px solid var(--color-border2)',
          }}
        >
          {/* Panel header */}
          <div style={{ padding: '1.4rem 1.4rem 1rem', borderBottom: '1px solid var(--color-border)' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', fontWeight: 500, color: 'var(--color-cream)', letterSpacing: '0.02em' }}>
              Path Planner
            </div>
          </div>

          {/* ── 3D Mapping summary ── */}
          {session.image_classifications?.length > 0 && (
            <MappingPanel
              classifications={session.image_classifications}
              summary={session.perspective_summary ?? {}}
              has3d={session.has_3d_data}
              mono={mono}
            />
          )}

          {/* ── AI Analysis ── */}
          {session.ai_analysis && <AiPanel ai={session.ai_analysis} mono={mono} />}

          {/* ── Waypoints ── */}
          <Section label="WAYPOINTS">
            {(['start', 'goal'] as const).map(type => {
              const point = type === 'start' ? start : goal
              const isActive = placing === type
              const accentColor = type === 'start' ? 'var(--color-go)' : 'var(--color-stop)'
              return (
                <div
                  key={type}
                  style={{
                    border: `1px solid ${isActive ? accentColor : 'var(--color-border2)'}`,
                    padding: '0.75rem 0.9rem',
                    marginBottom: '0.5rem',
                    background: isActive ? 'var(--color-surface2)' : 'transparent',
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span style={{ ...mono, fontSize: '0.62rem', letterSpacing: '0.2em', color: isActive ? accentColor : 'var(--color-faint)' }}>
                      {type.toUpperCase()}
                    </span>
                    <button
                      onClick={() => setPlacing(type)}
                      style={{
                        ...mono, fontSize: '0.6rem', letterSpacing: '0.18em',
                        padding: '0.3rem 0.7rem',
                        background: isActive ? accentColor : 'transparent',
                        color: isActive ? 'var(--color-base)' : 'var(--color-muted)',
                        border: `1px solid ${isActive ? accentColor : 'var(--color-border3)'}`,
                        cursor: 'pointer',
                      }}
                    >
                      {isActive ? 'ACTIVE' : 'SET'}
                    </button>
                  </div>
                  <div style={{ ...mono, fontSize: '0.65rem', color: 'var(--color-muted)', marginTop: '0.4rem', letterSpacing: '0.06em' }}>
                    {point ? `${point.row}, ${point.col}` : '—'}
                  </div>
                </div>
              )
            })}
          </Section>

          {/* ── Algorithm ── */}
          <Section label="ALGORITHM">
            {(['astar', 'dijkstra', 'rrt'] as Algorithm[]).map(a => (
              <button
                key={a}
                onClick={() => { setAlgorithm(a); setPath(null); setNoPath(false) }}
                className="w-full text-left transition-colors"
                style={{
                  ...mono, fontSize: '0.68rem', letterSpacing: '0.14em',
                  padding: '0.65rem 0.9rem',
                  background: algorithm === a ? 'var(--color-surface3)' : 'transparent',
                  color: algorithm === a ? 'var(--color-gold-dk)' : 'var(--color-muted)',
                  border: 'none',
                  borderLeft: `2px solid ${algorithm === a ? 'var(--color-gold)' : 'transparent'}`,
                  cursor: 'pointer',
                  display: 'block',
                  width: '100%',
                }}
                onMouseEnter={e => { if (algorithm !== a) (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-cream)' }}
                onMouseLeave={e => { if (algorithm !== a) (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-muted)' }}
              >
                {a === 'astar' ? 'A*' : a.charAt(0).toUpperCase() + a.slice(1)}
              </button>
            ))}
            <div style={{ ...mono, fontSize: '0.6rem', letterSpacing: '0.1em', color: 'var(--color-faint)', padding: '0.6rem 0.9rem 0' }}>
              {algoMeta[algorithm]}
            </div>
          </Section>

          {/* ── Compute ── */}
          <Section label="COMPUTE">
            <button
              onClick={compute}
              disabled={!start || !goal || computing}
              style={{
                ...mono, fontSize: '0.68rem', letterSpacing: '0.2em',
                width: '100%', padding: '0.8rem',
                background: (start && goal && !computing) ? 'var(--color-gold)' : 'var(--color-surface2)',
                color: (start && goal && !computing) ? 'var(--color-forest)' : 'var(--color-faint)',
                border: 'none',
                cursor: (start && goal && !computing) ? 'pointer' : 'not-allowed',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => { if (start && goal && !computing) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold-lt)' }}
              onMouseLeave={e => { if (start && goal && !computing) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold)' }}
            >
              {computing ? 'COMPUTING…' : 'FIND PATH'}
            </button>

            {noPath && (
              <div style={{ ...mono, fontSize: '0.62rem', letterSpacing: '0.1em', color: 'var(--color-stop)', marginTop: '0.75rem' }}>
                No viable path found. Try a different algorithm or points.
              </div>
            )}
            {path && (
              <div style={{ ...mono, fontSize: '0.62rem', letterSpacing: '0.1em', color: 'var(--color-go)', marginTop: '0.75rem' }}>
                {path.length} waypoints computed
              </div>
            )}
          </Section>

          {/* ── Export ── */}
          {path && (
            <Section label="EXPORT">
              <button
                onClick={() => exportPath(path, algorithm)}
                style={{
                  ...mono, fontSize: '0.65rem', letterSpacing: '0.18em',
                  width: '100%', padding: '0.7rem',
                  background: 'transparent',
                  color: 'var(--color-gold-dk)',
                  border: '1px solid var(--color-gold-dk)',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-gold)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-gold)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--color-gold-dk)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-gold-dk)' }}
              >
                WAYPOINTS.JSON
              </button>
            </Section>
          )}

          {/* ── Reset ── */}
          <div style={{ marginTop: 'auto', padding: '1rem 1.4rem', borderTop: '1px solid var(--color-border)' }}>
            <button
              onClick={reset}
              style={{
                ...mono, fontSize: '0.62rem', letterSpacing: '0.18em',
                color: 'var(--color-faint)', background: 'none', border: 'none', cursor: 'pointer',
              }}
              onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-stop)')}
              onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-faint)')}
            >
              RESET SESSION
            </button>
          </div>
        </aside>
      </div>
    </div>
  )
}

// ── 3D Mapping panel ──────────────────────────────────────────────────────────

const PERSP_LABEL: Record<string, string> = {
  top_down:      'TOP-DOWN',
  oblique_floor: 'OBLIQUE',
  eye_level:     'EYE-LEVEL',
  ceiling:       'CEILING',
}
const PERSP_COLOR: Record<string, string> = {
  top_down:      'var(--color-go)',
  oblique_floor: 'var(--color-gold)',
  eye_level:     '#7ec8e3',
  ceiling:       'var(--color-faint)',
}

function MappingPanel({
  classifications,
  summary,
  has3d,
  mono,
}: {
  classifications: ImageClassification[]
  summary: Record<string, number>
  has3d: boolean
  mono: React.CSSProperties
}) {
  return (
    <div style={{ padding: '1rem 1.4rem', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', letterSpacing: '0.26em', color: 'var(--color-faint)', marginBottom: '0.75rem' }}>
        3-AXIS MAPPING
      </div>

      {/* Axis indicator badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <span style={{
          ...mono, fontSize: '0.58rem', letterSpacing: '0.14em',
          padding: '0.2rem 0.55rem',
          background: has3d ? 'rgba(126,200,227,0.12)' : 'var(--color-surface2)',
          color: has3d ? '#7ec8e3' : 'var(--color-faint)',
          border: `1px solid ${has3d ? '#7ec8e3' : 'var(--color-border2)'}`,
        }}>
          {has3d ? 'X · Y · Z' : 'X · Y'}
        </span>
        <span style={{ ...mono, fontSize: '0.58rem', color: 'var(--color-faint)', letterSpacing: '0.08em' }}>
          {has3d ? 'walls mapped' : 'floor only'}
        </span>
      </div>

      {/* Per-image perspective chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginBottom: '0.6rem' }}>
        {classifications.map((c, i) => (
          <span
            key={i}
            title={`tilt ${c.tilt_from_vertical_deg}°  floor ${Math.round(c.floor_fraction * 100)}%`}
            style={{
              ...mono, fontSize: '0.52rem', letterSpacing: '0.1em',
              padding: '0.18rem 0.45rem',
              background: 'var(--color-surface2)',
              color: PERSP_COLOR[c.perspective] ?? 'var(--color-muted)',
              border: `1px solid ${PERSP_COLOR[c.perspective] ?? 'var(--color-border2)'}22`,
            }}
          >
            {PERSP_LABEL[c.perspective] ?? c.perspective.toUpperCase()}
            {c.wall_direction !== 'unknown' && ` ·${c.wall_direction.slice(0,1).toUpperCase()}`}
          </span>
        ))}
      </div>

      {/* Summary counts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.35rem 0.5rem' }}>
        {Object.entries(summary).map(([k, v]) => (
          <div key={k}>
            <div style={{ ...mono, fontSize: '0.5rem', letterSpacing: '0.14em', color: 'var(--color-faint)' }}>
              {PERSP_LABEL[k] ?? k.toUpperCase()}
            </div>
            <div style={{ ...mono, fontSize: '0.62rem', color: PERSP_COLOR[k] ?? 'var(--color-muted)' }}>
              {v} photo{v !== 1 ? 's' : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── AI Analysis panel ─────────────────────────────────────────────────────────

function AiPanel({ ai, mono }: { ai: AiAnalysis; mono: React.CSSProperties }) {
  const pct = (v: number) => `${Math.round(v * 100)}%`
  const rows: [string, string][] = [
    ['SPACE',       ai.space_type.replace('_', ' ').toUpperCase()],
    ['NAVIGABLE',   pct(ai.navigable_fraction)],
    ['OBSTACLES',   pct(ai.obstacle_density)],
    ['AXIS',        ai.primary_axis.toUpperCase()],
    ['ROTATION',    `${ai.orientation_correction}°`],
  ]
  return (
    <div style={{ padding: '1rem 1.4rem', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', letterSpacing: '0.26em', color: 'var(--color-faint)', marginBottom: '0.75rem' }}>
        AI ANALYSIS
      </div>
      {/* Description */}
      <p style={{ fontFamily: 'var(--font-sans)', fontSize: '0.72rem', color: 'var(--color-muted)', lineHeight: 1.55, marginBottom: '0.75rem', fontWeight: 300 }}>
        {ai.description}
      </p>
      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem 0.6rem' }}>
        {rows.map(([k, v]) => (
          <div key={k}>
            <div style={{ ...mono, fontSize: '0.52rem', letterSpacing: '0.18em', color: 'var(--color-faint)' }}>{k}</div>
            <div style={{ ...mono, fontSize: '0.62rem', color: 'var(--color-cream)', marginTop: '0.1rem' }}>{v}</div>
          </div>
        ))}
      </div>
      {/* Navigable bar */}
      <div style={{ marginTop: '0.75rem', height: '3px', background: 'var(--color-border2)', borderRadius: 0 }}>
        <div style={{ height: '100%', width: pct(ai.navigable_fraction), background: 'var(--color-go)', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: '1rem 1.4rem', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', letterSpacing: '0.26em', color: 'var(--color-faint)', marginBottom: '0.75rem' }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function exportPath(path: [number, number][], algo: string) {
  const data = { algorithm: algo, waypoints: path.map(([r, c]) => ({ row: r, col: c })) }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `anavi_path_${algo}.json`; a.click()
  URL.revokeObjectURL(url)
}
