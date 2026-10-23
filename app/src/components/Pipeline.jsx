import { Fragment, useEffect, useRef } from 'react'

export default function Pipeline({ steps, activeStepId, onSelect, stepStatus }) {
  const activeRef = useRef(null)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
  }, [activeStepId])

  return (
    <div className="pipeline" role="tablist" aria-label="Investigation flow">
      {steps.map((s, i) => {
        const status = stepStatus(s)
        return (
          <Fragment key={s.id}>
            {i > 0 && <span className={`pipe-seg seg-${stepStatus(steps[i - 1])}`} aria-hidden="true" />}
            <button
              ref={s.id === activeStepId ? activeRef : null}
              className={`pipe-node pn-${status} ${s.id === activeStepId ? 'active' : ''}`}
              onClick={() => onSelect(s.id)}
              title={`${s.num} · ${s.title}`}
              role="tab"
              aria-selected={s.id === activeStepId}
            >
              <span className="pipe-dot">{s.num}</span>
              <span className="pipe-label">{s.title}</span>
            </button>
          </Fragment>
        )
      })}
    </div>
  )
}
