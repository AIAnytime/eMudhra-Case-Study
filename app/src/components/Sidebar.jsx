import { useEffect, useRef, useState } from 'react'
import { PlayIcon, CheckIcon, Spinner } from './icons.jsx'

function runAllLabel(runAllState) {
  if (!runAllState) return null
  const { status, index, total, current } = runAllState
  if (status === 'running') return `${index + 1}/${total} · ${current}`
  if (status === 'done') return `all ${total} steps passed`
  if (status === 'blocked') return `stopped — prerequisites missing (${current})`
  return `stopped — failed at ${current}`
}

function StepItem({ step, active, status, onSelect, collapsed }) {
  return (
    <button
      className={`step-item ${active ? 'active' : ''}`}
      onClick={() => onSelect(step.id)}
      title={collapsed ? `${step.num} · ${step.title}` : undefined}
    >
      <span className={`step-status st-${status}`} />
      <span className="step-index">{step.num}</span>
      <span className="step-title">{step.title}</span>
    </button>
  )
}

export default function Sidebar({ steps, activeStepId, onSelect, stepStatus, target, workspace, collapsed, onToggle, runAllState, onRunAll }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  const openFolder = () => {
    fetch('/api/open-workspace', { method: 'POST' }).catch(() => {})
    setMenuOpen(false)
  }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-top">
        <button
          className="sidebar-toggle"
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <span className="brand-mark">eM</span>
        </button>
      </div>

      {!collapsed && (
        <div className="target-block">
          <label>Target host</label>
          <input value={target} readOnly spellCheck={false} />
        </div>
      )}

      {!collapsed && (
        <div className="run-all-block">
          <button
            className={`run-all-btn ${runAllState?.status || ''}`}
            onClick={onRunAll}
            disabled={runAllState?.status === 'running'}
            title="Run all steps in sequence"
          >
            {runAllState?.status === 'running' ? <Spinner /> : runAllState?.status === 'done' ? <CheckIcon /> : <PlayIcon />}
            <span>Run all</span>
          </button>
          {runAllLabel(runAllState) && (
            <div className={`run-all-status ras-${runAllState.status}`}>{runAllLabel(runAllState)}</div>
          )}
        </div>
      )}

      {!collapsed && <div className="steps-label">Investigation steps</div>}
      <nav className="steps-list">
        {steps.map((s) => (
          <StepItem
            key={s.id}
            step={s}
            active={s.id === activeStepId}
            status={stepStatus(s)}
            onSelect={onSelect}
            collapsed={collapsed}
          />
        ))}
      </nav>

      <div className="profile" ref={menuRef}>
        {menuOpen && (
          <div className="profile-menu">
            <div className="profile-menu-head">
              <strong>Investigator</strong>
              <span>local session</span>
            </div>
            <div className="profile-menu-path" title={workspace}>{workspace}</div>
            <button onClick={openFolder}>Open workspace folder</button>
          </div>
        )}
        <button className="profile-btn" onClick={() => setMenuOpen((v) => !v)} title="Investigator">
          <span className="avatar">IN</span>
          {!collapsed && (
            <>
              <span className="profile-meta">
                <strong>Investigator</strong>
                <span>localhost</span>
              </span>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className={menuOpen ? 'chev up' : 'chev'}>
                <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
