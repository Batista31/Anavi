import { useState, useCallback, useRef } from 'react'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { processImages } from '../api'
import type { ProcessResponse } from '../api'
import { useTheme } from '../useTheme'
import ThemeToggle from '../components/ThemeToggle'

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'])
const isImage = (f: File) => IMAGE_EXTS.has('.' + f.name.split('.').pop()!.toLowerCase())

/* ── Shared style tokens ── */
const mono = { fontFamily: 'var(--font-mono)' } as const
const display = { fontFamily: 'var(--font-display)' } as const
const sans = { fontFamily: 'var(--font-sans)' } as const

export default function Upload() {
  const nav = useNavigate()
  const [theme, toggleTheme] = useTheme()
  useScrollReveal()
  const [files, setFiles] = useState<File[]>([])
  const [status, setStatus] = useState<'idle' | 'processing' | 'error'>('idle')
  const [error, setError] = useState('')
  const folderRef = useRef<HTMLInputElement>(null)
  const filesRef  = useRef<HTMLInputElement>(null)

  const addFiles = useCallback((incoming: File[]) => {
    const imgs = incoming.filter(isImage)
    setFiles(prev => {
      const seen = new Set(prev.map(f => f.name))
      return [...prev, ...imgs.filter(f => !seen.has(f.name))]
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: addFiles, accept: { 'image/*': [] }, multiple: true, noClick: true,
  })

  const fromInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files))
    e.target.value = ''
  }

  const handleProcess = async () => {
    if (!files.length || status === 'processing') return
    setStatus('processing')
    setError('')
    try {
      const result: ProcessResponse = await processImages(files)
      sessionStorage.setItem('anavi_session', JSON.stringify(result))
      nav('/viewer')
    } catch (e: any) {
      console.error('[ANAVI] process error:', e)
      console.error('[ANAVI] response:', e?.response)
      console.error('[ANAVI] message:', e?.message)
      const detail = e?.response?.data?.detail
        ?? e?.message
        ?? 'Processing failed. Is the backend running?'
      setError(detail)
      setStatus('error')
    }
  }

  const totalMB = (files.reduce((s, f) => s + f.size, 0) / 1024 / 1024).toFixed(1)
  const ready = files.length > 0 && status !== 'processing'

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--color-base)', color: 'var(--color-cream)' }}>

      {/* ── Top bar — dark green ── */}
      <header className="flex items-center justify-between px-10 py-5" style={{ background: 'var(--color-forest)', borderBottom: '1px solid var(--color-forest-lt)' }}>
        <button
          onClick={() => nav('/')}
          style={{ ...mono, fontSize: '0.68rem', letterSpacing: '0.2em', color: 'var(--color-forest-text)', background: 'none', border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-cream)')}
          onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-forest-text)')}
        >
          ← ANAVI
        </button>
        <div className="flex items-center gap-4">
          <ThemeToggle theme={theme} toggle={toggleTheme} />
          <span style={{ ...mono, fontSize: '0.68rem', letterSpacing: '0.2em', color: 'var(--color-forest-faint)' }}>
            STEP 1 OF 2 · IMAGE IMPORT
          </span>
        </div>
      </header>

      {/* ── Body ── */}
      <main className="flex-1 flex flex-col" style={{ maxWidth: '820px', margin: '0 auto', width: '100%', padding: '4rem 2.5rem' }}>

        {/* Hidden inputs */}
        <input ref={folderRef} type="file" className="hidden"
          // @ts-ignore
          webkitdirectory="" multiple onChange={fromInput} />
        <input ref={filesRef}  type="file" className="hidden" multiple
          accept=".jpg,.jpeg,.png,.tiff,.tif,.bmp,.webp" onChange={fromInput} />

        {/* Heading */}
        <h1 className="reveal" style={{ ...display, fontSize: '2.6rem', fontWeight: 500, lineHeight: 1.1, marginBottom: '0.6rem', letterSpacing: '-0.01em' }}>
          Import photographs
        </h1>
        <p className="reveal reveal-d1" style={{ ...sans, fontSize: '0.9rem', fontWeight: 300, color: 'var(--color-muted)', lineHeight: 1.75, marginBottom: '3rem', maxWidth: '480px' }}>
          Overlapping photos of the target space — a room, corridor, society layout, or outdoor area.
          The more overlap between shots, the better the stitched map.
        </p>

        {/* ── Two input options ── */}
        <div className="grid grid-cols-2 gap-px reveal reveal-d2" style={{ background: 'var(--color-border2)', border: '1px solid var(--color-border2)', marginBottom: '1px' }}>
          {[
            { label: 'Select Folder', sub: 'Import an entire directory', ref: folderRef },
            { label: 'Select Files',  sub: 'Import individual images',   ref: filesRef  },
          ].map(({ label, sub, ref }) => (
            <button
              key={label}
              onClick={() => ref.current?.click()}
              className="flex flex-col justify-center py-10 px-8 transition-colors text-left"
              style={{ background: 'var(--color-surface)', gap: '0.4rem', border: 'none', cursor: 'pointer' }}
              onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-surface2)')}
              onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.background = 'var(--color-surface)')}
            >
              <span style={{ ...mono, fontSize: '0.68rem', letterSpacing: '0.2em', color: 'var(--color-gold-dk)' }}>
                {label.toUpperCase()}
              </span>
              <span style={{ ...sans, fontSize: '0.82rem', fontWeight: 300, color: 'var(--color-muted)', marginTop: '0.2rem' }}>
                {sub}
              </span>
            </button>
          ))}
        </div>

        {/* ── Drag zone ── */}
        <div
          {...getRootProps()}
          className="flex items-center justify-center transition-colors reveal reveal-d3"
          style={{
            border: `1px dashed ${isDragActive ? 'var(--color-gold)' : 'var(--color-border2)'}`,
            background: isDragActive ? 'var(--color-surface2)' : 'transparent',
            padding: '1.4rem',
            cursor: 'default',
          }}
        >
          <input {...getInputProps()} />
          <span style={{ ...mono, fontSize: '0.65rem', letterSpacing: '0.22em', color: isDragActive ? 'var(--color-gold)' : 'var(--color-faint)' }}>
            {isDragActive ? 'RELEASE TO ADD' : 'OR DRAG FILES / FOLDERS HERE'}
          </span>
        </div>

        {/* ── File manifest ── */}
        {files.length > 0 && (
          <div style={{ marginTop: '2.5rem' }}>
            {/* Header row */}
            <div className="flex justify-between items-center" style={{ marginBottom: '0.75rem' }}>
              <span style={{ ...mono, fontSize: '0.65rem', letterSpacing: '0.2em', color: 'var(--color-gold-dk)' }}>
                {files.length} IMAGE{files.length !== 1 ? 'S' : ''} · {totalMB} MB
              </span>
              <button
                onClick={() => setFiles([])}
                style={{ ...mono, fontSize: '0.65rem', letterSpacing: '0.18em', color: 'var(--color-faint)', background: 'none', border: 'none', cursor: 'pointer' }}
                onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-stop)')}
                onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-faint)')}
              >
                CLEAR ALL
              </button>
            </div>

            {/* File list as a bordered table */}
            <div
              className="overflow-y-auto"
              style={{ maxHeight: '200px', border: '1px solid var(--color-border)' }}
            >
              {files.map((f, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between group"
                  style={{
                    padding: '0.55rem 0.9rem',
                    borderBottom: i < files.length - 1 ? '1px solid var(--color-border)' : 'none',
                    background: 'var(--color-surface)',
                  }}
                >
                  <span style={{ ...mono, fontSize: '0.72rem', color: 'var(--color-cream)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
                    {f.name}
                  </span>
                  <div className="flex items-center gap-4">
                    <span style={{ ...mono, fontSize: '0.65rem', color: 'var(--color-faint)' }}>
                      {(f.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      onClick={() => setFiles(p => p.filter((_, j) => j !== i))}
                      style={{ ...mono, fontSize: '0.65rem', color: 'var(--color-faint)', background: 'none', border: 'none', cursor: 'pointer', opacity: 0 }}
                      className="group-hover:opacity-100 transition-opacity"
                      onMouseEnter={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-stop)')}
                      onMouseLeave={e => ((e.currentTarget as HTMLButtonElement).style.color = 'var(--color-faint)')}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div style={{ ...mono, fontSize: '0.72rem', letterSpacing: '0.08em', color: 'var(--color-stop)', border: '1px solid var(--color-stop)', padding: '0.9rem 1.1rem', marginTop: '1.5rem' }}>
            {error}
          </div>
        )}

        {/* ── CTA ── */}
        <div className="flex items-center gap-6" style={{ marginTop: '2.5rem' }}>
          <button
            onClick={handleProcess}
            disabled={!ready}
            style={{
              ...mono,
              fontSize: '0.72rem',
              letterSpacing: '0.2em',
              padding: '0.85rem 2.4rem',
              background: ready ? 'var(--color-gold)' : 'var(--color-surface2)',
              color: ready ? 'var(--color-forest)' : 'var(--color-faint)',
              border: 'none',
              cursor: ready ? 'pointer' : 'not-allowed',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { if (ready) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold-lt)' }}
            onMouseLeave={e => { if (ready) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-gold)' }}
          >
            {status === 'processing' ? 'STITCHING…' : 'GENERATE MAP'}
          </button>
          {status === 'processing' && (
            <span style={{ ...mono, fontSize: '0.65rem', letterSpacing: '0.18em', color: 'var(--color-muted)' }}>
              Processing {files.length} images
            </span>
          )}
        </div>
      </main>
    </div>
  )
}
