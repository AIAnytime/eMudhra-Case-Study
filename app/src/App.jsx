import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Pipeline from './components/Pipeline.jsx'
import CommandCard from './components/CommandCard.jsx'
import EvidenceDrawer from './components/EvidenceDrawer.jsx'
import { SunIcon, MoonIcon } from './components/icons.jsx'

const EMPTY_RUN = { lines: [], status: 'idle', code: null, durationMs: null, log: null }

export default function App() {
  const [boot, setBoot] = useState(null)
  const [error, setError] = useState(null)
  const [activeStepId, setActiveStepId] = useState('step-0')
  const [runs, setRuns] = useState({})
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [fileView, setFileView] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('emudhra.sidebar') === 'collapsed',
  )
  const [theme, setTheme] = useState(() => localStorage.getItem('emudhra.theme') || 'dark')
  const [runAllState, setRunAllState] = useState(null)
  const sourcesRef = useRef({})
  const runAllRef = useRef(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('emudhra.theme', theme)
  }, [theme])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      localStorage.setItem('emudhra.sidebar', prev ? 'expanded' : 'collapsed')
      return !prev
    })
  }, [])

  useEffect(() => {
    fetch('/api/steps')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`backend ${r.status}`))))
      .then(setBoot)
      .catch((e) => setError(String(e)))
  }, [])

  const refreshSteps = useCallback(() => {
    fetch('/api/steps').then((r) => (r.ok ? r.json() : null)).then((d) => d && setBoot(d))
  }, [])

  const patchRun = useCallback((key, patch) => {
    setRuns((prev) => ({ ...prev, [key]: { ...(prev[key] || EMPTY_RUN), ...patch } }))
  }, [])

  const appendLines = useCallback((key, chunks) => {
    setRuns((prev) => {
      const cur = prev[key] || EMPTY_RUN
      return { ...prev, [key]: { ...cur, lines: cur.lines.concat(chunks) } }
    })
  }, [])

  const execute = useCallback(
    (stepId, cmd, onDone) => {
      const key = `${stepId}:${cmd.id}`
      const existing = sourcesRef.current[key]
      if (existing) existing.close()
      patchRun(key, { ...EMPTY_RUN, status: 'running' })
      const es = new EventSource(`/api/run/stream?step=${encodeURIComponent(stepId)}&cmd=${encodeURIComponent(cmd.id)}`)
      sourcesRef.current[key] = es

      const finish = (final) => {
        es.close()
        delete sourcesRef.current[key]
        refreshSteps()
        if (onDone) onDone(final)
      }

      es.onmessage = (ev) => {
        const msg = JSON.parse(ev.data)
        if (msg.t === 'start') {
          patchRun(key, { status: 'running', lines: [] })
        } else if (msg.t === 'note') {
          appendLines(key, [`\u2139 ${msg.data}\n`])
        } else if (msg.t === 'line') {
          appendLines(key, [msg.data])
        } else if (msg.t === 'exit') {
          const final = {
            status: msg.blocked ? 'blocked' : msg.exitCode === 0 ? 'ok' : 'failed',
            code: msg.exitCode,
            durationMs: msg.durationMs,
            log: msg.log || null,
          }
          patchRun(key, final)
          finish(final)
        } else if (msg.t === 'error') {
          appendLines(key, [`\u2717 ${msg.message}\n`])
          patchRun(key, { status: 'failed' })
          finish({ status: 'failed' })
        }
      }
      es.onerror = () => {
        setRuns((prev) => {
          const cur = prev[key] || EMPTY_RUN
          const lines = cur.lines.length ? cur.lines : ['\u2717 lost connection to local backend\n']
          return { ...prev, [key]: { ...cur, status: 'failed', lines } }
        })
        finish({ status: 'failed' })
      }
    },
    [appendLines, patchRun, refreshSteps],
  )

  const runCommand = useCallback((stepId, cmd) => execute(stepId, cmd), [execute])

  useEffect(() => () => Object.values(sourcesRef.current).forEach((es) => es.close()), [])

  const steps = boot?.steps || []
  const activeStep = useMemo(
    () => steps.find((s) => s.id === activeStepId) || steps[0],
    [steps, activeStepId],
  )
  const chainRunning = runAllState?.status === 'running'

  const runAll = useCallback(async () => {
    if (runAllRef.current || !steps.length) return
    runAllRef.current = true
    const queue = steps.flatMap((s) => s.commands.map((c) => ({ s, c })))
    setRunAllState({ status: 'running', index: 0, total: queue.length, current: '' })
    for (let i = 0; i < queue.length; i++) {
      const { s, c } = queue[i]
      setActiveStepId(s.id)
      setRunAllState({ status: 'running', index: i, total: queue.length, current: `${s.num} · ${c.label}` })
      const res = await new Promise((resolve) => execute(s.id, c, resolve))
      if (res.status !== 'ok') {
        setRunAllState({ status: res.status, index: i, total: queue.length, current: `${s.num} · ${c.label}` })
        runAllRef.current = false
        return
      }
    }
    setRunAllState({ status: 'done', index: queue.length, total: queue.length, current: '' })
    runAllRef.current = false
  }, [execute, steps])

  const stepStatus = useCallback(
    (step) => {
      const st = step.commands.map((c) => (runs[`${step.id}:${c.id}`] || EMPTY_RUN).status)
      if (st.includes('running')) return 'running'
      if (st.length && st.every((s) => s === 'ok')) return 'ok'
      if (st.includes('failed') || st.includes('blocked')) return 'failed'
      if (st.includes('ok')) return 'partial'
      return 'idle'
    },
    [runs],
  )

  const openFile = useCallback((path) => {
    fetch(`/api/evidence/file?path=${encodeURIComponent(path)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setFileView(d))
      .catch((e) => setFileView({ path, content: `failed to load: ${e.message}` }))
  }, [])

  if (error) {
    return (
      <div className="boot-error">
        <h1>eMudhra Workbench</h1>
        <p>Cannot reach the local backend.</p>
        <code>cd server &amp;&amp; ./.venv/bin/python server.py</code>
        <small>{error}</small>
      </div>
    )
  }
  if (!boot || !activeStep) return <div className="boot-loading">Loading workbench…</div>

  return (
    <div className="shell">
      <Sidebar
        steps={steps}
        activeStepId={activeStep.id}
        onSelect={setActiveStepId}
        stepStatus={stepStatus}
        target={boot.target}
        workspace={boot.workspace}
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
        runAllState={runAllState}
        onRunAll={runAll}
      />
      <main className="main">
        <header className="step-header">
          <div className="step-heading">
            <span className="step-num">{String(activeStep.num).padStart(2, '0')}</span>
            <div>
              <h1>{activeStep.title}</h1>
              <p>{activeStep.summary}</p>
            </div>
          </div>
          <div className="header-actions">
            <button
              className="ghost-btn icon-only"
              onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            </button>
            <button className="ghost-btn" onClick={() => setDrawerOpen(true)}>
              Evidence
            </button>
          </div>
        </header>

        <Pipeline steps={steps} activeStepId={activeStep.id} onSelect={setActiveStepId} stepStatus={stepStatus} />

        <div className="content-grid">
          <section className="commands">
            {activeStep.commands.map((c) => (
              <CommandCard
                key={c.id}
                stepId={activeStep.id}
                cmd={c}
                run={runs[`${activeStep.id}:${c.id}`] || EMPTY_RUN}
                onRun={runCommand}
                chainRunning={chainRunning}
              />
            ))}
          </section>
          <aside className="explain">
            <h2>What this step shows</h2>
            {activeStep.explain.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </aside>
        </div>

        <footer className="footer">
          <span className="footer-left">
            LOCAL MODE · backend <span className="dot-online" /> localhost:8000 · workspace ~/eMudhra
          </span>
          <span className="footer-right">Built by AI Anytime</span>
        </footer>
      </main>

      {drawerOpen && (
        <EvidenceDrawer
          onClose={() => setDrawerOpen(false)}
          onOpenFile={openFile}
          workspace={boot.workspace}
        />
      )}
      {fileView && (
        <div className="file-modal" onClick={() => setFileView(null)}>
          <div className="file-modal-inner" onClick={(e) => e.stopPropagation()}>
            <div className="file-modal-head">
              <span className="file-modal-path">~/eMudhra/{fileView.path}</span>
              <button className="ghost-btn" onClick={() => setFileView(null)}>Close</button>
            </div>
            <pre className="file-modal-body">{fileView.content}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
