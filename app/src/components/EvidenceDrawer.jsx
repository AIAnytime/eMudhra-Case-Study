import { useEffect, useState } from 'react'

const GROUPS = [
  { prefix: 'certificates/', label: 'Certificates' },
  { prefix: 'evidence/runs/', label: 'Run logs' },
  { prefix: 'evidence/', label: 'Evidence' },
  { prefix: 'reports/', label: 'Reports' },
]

export default function EvidenceDrawer({ onClose, onOpenFile, workspace }) {
  const [files, setFiles] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      fetch('/api/evidence')
        .then((r) => (r.ok ? r.json() : { files: [] }))
        .then((d) => alive && setFiles(d.files))
    load()
    const t = setInterval(load, 4000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  const grouped = GROUPS.map((g) => ({
    ...g,
    files: (files || []).filter((f) => f.path.startsWith(g.prefix) && !GROUPS.some((o) => o !== g && f.path.startsWith(o.prefix) && o.prefix.length > g.prefix.length)),
  })).filter((g) => g.files.length > 0)

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <h2>Evidence</h2>
            <span className="drawer-path">{workspace}</span>
          </div>
          <button className="ghost-btn" onClick={onClose}>Close</button>
        </div>
        <div className="drawer-body">
          {files === null && <p className="drawer-empty">Loading…</p>}
          {files !== null && files.length === 0 && <p className="drawer-empty">No evidence captured yet — run a step first.</p>}
          {grouped.map((g) => (
            <div key={g.label} className="drawer-group">
              <h3>{g.label}</h3>
              {g.files.map((f) => (
                <button key={f.path} className="drawer-file" onClick={() => onOpenFile(f.path)}>
                  <span className="drawer-file-name">{f.path}</span>
                  <span className="drawer-file-meta">{f.size} B</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </aside>
    </div>
  )
}
