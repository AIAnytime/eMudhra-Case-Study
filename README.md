# eMudhra — Certificate Security Investigation Workbench

A local command-runner for the live certificate investigation. All commands from
the runbook are preloaded: select a step, click **Run**, and the real terminal
output streams into the panel — nothing is typed or fabricated live.

## Run it

```bash
cd "eMudhra Case Study/server"
../.venv/bin/python server.py
```

Then open http://localhost:8000.

The first time only, set the environment up with:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r server/requirements.txt
cd app && npm install && npm run build   # frontend build (already built)
```

For frontend development instead: `cd app && npm run dev` (proxies `/api` to
port 8000) and run the backend alongside.

## How it works

- **Backend** — FastAPI (`server/server.py`). Executes only the fixed registry
  in `server/steps_registry.py` via `subprocess` (`bash -c`, cwd `~/eMudhra`),
  streams stdout/stderr over SSE, and persists every run (command, timestamp,
  exit code, duration) to `~/eMudhra/evidence/runs/`.
- **Frontend** — React + Vite (`app/`). Sidebar with steps 0–7, command cards
  with readonly command preview + Run, live terminal panel, "What this step
  shows" explanation rail, and an Evidence drawer for certificates, evidence
  and reports.
- **Workspace** — `~/eMudhra/{certificates,evidence,reports}`.

Steps that need certificate files (2–6) are gated: the backend checks
prerequisites and reports exactly what is missing. Place the article's test
certificates under `~/eMudhra/certificates/article/` to unlock steps 4–5.

Built by AI Anytime
