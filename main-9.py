import json
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

EMAIL = "businessmakers662@gmail.com"
STARTED = time.monotonic()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_request_count = 0
_logs = deque(maxlen=2000)


def _log(entry: dict) -> None:
    with _lock:
        _logs.append(entry)
    # Structured JSON line on stdout so the host's log viewer shows it too.
    print(json.dumps(entry), file=sys.stdout, flush=True)


@app.middleware("http")
async def observe(request: Request, call_next):
    global _request_count
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    with _lock:
        _request_count += 1  # counts every request to any endpoint
    status = 500
    level = "info"
    try:
        response = await call_next(request)
        status = response.status_code
        level = "error" if status >= 500 else "warning" if status >= 400 else "info"
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        level = "error"
        raise
    finally:
        _log(
            {
                "level": level,
                "ts": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path,
                "method": request.method,
                "status": status,
                "request_id": request_id,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
            }
        )


@app.get("/work")
def work(n: int = Query(1, ge=0, le=1_000_000)):
    acc = 0
    for i in range(n):  # K units of real work
        acc += i * i
    return {"email": EMAIL, "done": n}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    with _lock:
        count = _request_count
    body = (
        "# HELP http_requests_total Total HTTP requests received.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {count}\n"
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "uptime_s": round(time.monotonic() - STARTED, 3)}


@app.get("/logs/tail")
def logs_tail(limit: int = Query(50, ge=0, le=2000)):
    with _lock:
        items = list(_logs)
    return items[-limit:] if limit else []


@app.get("/")
def root():
    return {"status": "ok"}
