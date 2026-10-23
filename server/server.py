"""eMudhra Certificate Security Investigation Workbench — local backend.

Executes only the predefined commands in steps_registry.py. Each run is
streamed over SSE, and every run's full output (with timestamp, command,
exit code and duration) is persisted under ~/eMudhra/evidence/runs/.
"""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from steps_registry import STEPS, INDEX, TARGET_HOST

WORKSPACE = Path.home() / "eMudhra"
RUN_TIMEOUT_S = 120

app = FastAPI(title="eMudhra Investigation Workbench")
RUNS = []  # most recent first, kept in memory for the status rail


def ensure_workspace():
    for d in ("certificates", "evidence", "evidence/runs", "reports"):
        (WORKSPACE / d).mkdir(parents=True, exist_ok=True)


ensure_workspace()


def ws_path(rel: str) -> Path:
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise HTTPException(status_code=400, detail="path escapes workspace")
    return p


def serialize_steps():
    out = []
    for s in STEPS:
        sc = dict(s)
        sc["commands"] = []
        for c in s["commands"]:
            cc = dict(c)
            cc["missing"] = [r for r in c.get("requires", []) if not ws_path(r).exists()]
            sc["commands"].append(cc)
        out.append(sc)
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "workspace": str(WORKSPACE), "target": TARGET_HOST}


@app.get("/api/steps")
def steps():
    return {"workspace": str(WORKSPACE), "target": TARGET_HOST, "steps": serialize_steps()}


@app.get("/api/runs")
def runs():
    return RUNS[:100]


@app.get("/api/evidence")
def evidence():
    ensure_workspace()
    files = []
    seen = set()
    for sub in ("certificates", "evidence", "reports"):
        base = WORKSPACE / sub
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(WORKSPACE))
            if rel in seen:
                continue
            seen.add(rel)
            st = p.stat()
            files.append(
                {
                    "path": rel,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                }
            )
    files.sort(key=lambda f: f["path"])
    return {"workspace": str(WORKSPACE), "files": files}


@app.get("/api/evidence/file")
def evidence_file(path: str = Query(...)):
    p = ws_path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="not found")
    if p.stat().st_size > 512 * 1024:
        raise HTTPException(status_code=413, detail="file too large to preview")
    return {"path": path, "content": p.read_text(errors="replace")}


@app.post("/api/open-workspace")
def open_workspace():
    subprocess.Popen(["open", str(WORKSPACE)])
    return {"opened": str(WORKSPACE)}


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def run_stream(step_id: str, cmd_id: str):
    found = INDEX.get((step_id, cmd_id))
    run_id = uuid.uuid4().hex[:12]
    if not found:
        yield sse({"t": "error", "message": "unknown step/command"})
        return
    step, cmd = found

    started_ts = time.time()
    started_at = datetime.now(timezone.utc)
    header = (
        f"$ {cmd['cmd']}\n"
        f"# step {step['num']} · {cmd['label']}\n"
        f"# started: {started_at.isoformat()}\n"
        f"# workspace: {WORKSPACE}\n\n"
    )

    missing = [r for r in cmd.get("requires", []) if not ws_path(r).exists()]
    if missing:
        rec = {
            "runId": run_id,
            "step": step_id,
            "cmd": cmd_id,
            "label": cmd["label"],
            "exitCode": None,
            "startedAt": started_at.isoformat(),
            "durationMs": 0,
            "blocked": True,
        }
        RUNS.insert(0, rec)
        msg = cmd.get("requiresNote", "Missing prerequisites: " + ", ".join(missing))
        yield sse({"t": "start", "runId": run_id, "command": cmd["cmd"], "blocked": True})
        yield sse({"t": "line", "data": f"BLOCKED — prerequisite files missing:\n"})
        for m in missing:
            yield sse({"t": "line", "data": f"  ✗ {m}\n"})
        yield sse({"t": "line", "data": f"\n{msg}\n"})
        yield sse({"t": "exit", "exitCode": None, "blocked": True, "durationMs": 0})
        return

    command = cmd["cmd"]
    if cmd.get("fallback") and subprocess.call(["which", command.split()[0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        yield sse({"t": "note", "data": cmd.get("fallback_note", "primary tool missing — running fallback command")})
        command = cmd["fallback"]

    yield sse({"t": "start", "runId": run_id, "command": command, "blocked": False})

    log_path = WORKSPACE / "evidence" / "runs" / f"{int(started_ts)}_{step['num']}-{cmd_id}.log"
    output_parts = [header]
    timed_out = False

    def feed(line):
        output_parts.append(line)
        return sse({"t": "line", "data": line})

    proc = None
    try:
        proc = subprocess.Popen(
            ["/bin/bash", "-c", command],
            cwd=WORKSPACE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        while True:
            if time.time() - started_ts > RUN_TIMEOUT_S:
                timed_out = True
                proc.kill()
            line = proc.stdout.readline()
            if not line:
                break
            yield feed(line)
        code = proc.wait()
    except Exception as e:  # surface backend failures instead of hanging the stream
        code = -1
        yield feed(f"\n[backend error: {e}]\n")
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()

    duration_ms = int((time.time() - started_ts) * 1000)
    if timed_out:
        code = -9
        yield feed(f"\n[killed after {RUN_TIMEOUT_S}s timeout]\n")

    log_path.write_text("".join(output_parts) + f"\n# exit code: {code}\n# duration: {duration_ms} ms\n")
    rec = {
        "runId": run_id,
        "step": step_id,
        "cmd": cmd_id,
        "label": cmd["label"],
        "exitCode": code,
        "startedAt": started_at.isoformat(),
        "durationMs": duration_ms,
        "log": str(log_path.relative_to(WORKSPACE)),
    }
    RUNS.insert(0, rec)
    yield sse({"t": "exit", **rec})


@app.get("/api/run/stream")
def run(step: str = Query(...), cmd: str = Query(...)):
    return StreamingResponse(
        run_stream(step, cmd),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve the built React app if it exists (production mode: only the backend runs).
dist = Path(__file__).resolve().parent.parent / "app" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    print(f"eMudhra workbench → http://localhost:8000  (workspace: {WORKSPACE})")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
