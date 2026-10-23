import { useEffect, useRef, useState } from 'react'
import { PlayIcon, CopyIcon, CheckIcon, Spinner } from './icons.jsx'

function Terminal({ run }) {
  const bodyRef = useRef(null)
  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [run.lines.length, run.status])

  return (
    <div className="terminal">
      <div className="terminal-head">
        <span className={`tstatus ts-${run.status}`}>
          {run.status === 'running' && <span className="pulse" />}
          {run.status === 'running'
            ? 'running'
            : run.status === 'ok'
              ? `exit 0 · ${run.durationMs} ms`
              : run.status === 'failed'
                ? `exit ${run.code} · ${run.durationMs} ms`
                : run.status === 'blocked'
                  ? 'blocked'
                  : ''}
        </span>
        {run.log && <span className="tlog">saved → {run.log}</span>}
      </div>
      <div className="terminal-body" ref={bodyRef}>
        {run.lines.map((l, i) => (
          <span key={i} className="tline">{l}</span>
        ))}
        {run.status === 'running' && <span className="tline cursor-line">▋</span>}
      </div>
    </div>
  )
}

export default function CommandCard({ stepId, cmd, run, onRun, chainRunning }) {
  const [copied, setCopied] = useState(false)
  const blockedByPrereq = cmd.missing?.length > 0 && run.status === 'idle'

  const copy = () => {
    navigator.clipboard.writeText(cmd.cmd).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    })
  }

  return (
    <article className={`cmd-card ${run.status !== 'idle' ? 'has-run' : ''}`}>
      <div className="cmd-head">
        <span className="cmd-id">{cmd.id}</span>
        <h3>{cmd.label}</h3>
        <span className={`cmd-state cs-${run.status}`}>
          {run.status === 'ok' ? 'passed' : run.status === 'failed' ? 'failed' : run.status === 'blocked' ? 'blocked' : run.status === 'running' ? 'running' : ''}
        </span>
      </div>

      <div className="cmd-preview">
        <pre><code>{cmd.cmd}</code></pre>
        <div className="cmd-actions">
          <button
            className={`icon-btn copy-btn ${copied ? 'copied' : ''}`}
            onClick={copy}
            title={copied ? 'Copied' : 'Copy command'}
            aria-label={copied ? 'Copied' : 'Copy command'}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </button>
          <button
            className={`icon-btn run-btn ${run.status === 'running' ? 'running' : ''}`}
            onClick={() => onRun(stepId, cmd)}
            disabled={run.status === 'running' || chainRunning}
            title={run.status === 'running' ? 'Running' : run.status === 'failed' || run.status === 'blocked' ? 'Retry' : 'Run'}
            aria-label={run.status === 'running' ? 'Running' : run.status === 'failed' || run.status === 'blocked' ? 'Retry command' : 'Run command'}
          >
            {run.status === 'running' ? <Spinner /> : <PlayIcon />}
          </button>
        </div>
      </div>

      {cmd.breakdown?.length > 0 && (
        <table className="cmd-breakdown">
          <thead>
            <tr><th>option</th><th>explanation</th></tr>
          </thead>
          <tbody>
            {cmd.breakdown.map(([opt, expl], i) => (
              <tr key={i}>
                <td className="bd-opt"><code>{opt}</code></td>
                <td className="bd-expl">{expl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="cmd-note">{cmd.note}</p>
      {blockedByPrereq && <p className="cmd-prereq">Needs: {cmd.missing.join(', ')}</p>}

      {run.status !== 'idle' && <Terminal run={run} />}
    </article>
  )
}
