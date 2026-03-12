"""
Web UI para el pipeline B2B Demand Generation.

Corre con:
    cd b2b_demand_gen
    uvicorn web_app:app --reload --port 8000

O desde la raíz del proyecto:
    uvicorn b2b_demand_gen.web_app:app --reload --port 8000
"""

import asyncio
import json
import os
import queue
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

# Asegurar que los imports del proyecto funcionen correctamente
_BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(_BASE_DIR))
load_dotenv(_BASE_DIR / ".env")

from agents.copy_blog import run_copy_blog
from agents.copy_industries import run_copy_industries
from agents.copy_services import run_copy_services
from agents.keyword_research import run_keyword_research
from agents.webflow_uploader import run_webflow_upload

OUTPUTS_DIR = _BASE_DIR / "outputs"
TEMPLATES_DIR = _BASE_DIR / "templates"

COPY_AGENTS = {
    "service": run_copy_services,
    "industry": run_copy_industries,
    "blog": run_copy_blog,
}

# ─── Estado en memoria de los jobs ───────────────────────────────────────────
# job_id → { queue, review_event, review_approved, status }
_jobs: dict[str, dict] = {}

app = FastAPI(title="B2B Content Generator")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _save_output(data: dict, filename: str) -> str:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    filepath = OUTPUTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filepath)


def _run_pipeline(job_id: str, params: dict):
    """Pipeline completo corriendo en un thread de fondo."""
    q = _jobs[job_id]["queue"]

    def emit(event_type: str, data: dict):
        q.put({"type": event_type, "data": data})

    try:
        topic = params["topic"]
        page_type = params.get("page_type", "service")
        target_market = params.get("target_market", "empresas B2B medianas y grandes")
        company_context = params.get("company_context", "")
        site_id = params.get("site_id") or os.environ.get("WEBFLOW_SITE_ID")
        collection_id = params.get("collection_id") or os.environ.get("WEBFLOW_COLLECTION_ID")
        auto_publish = params.get("auto_publish", False)
        skip_upload = params.get("skip_upload", False)
        skip_review = params.get("skip_review", False)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30]

        # ── PASO 1: Keyword Research ──────────────────────────────────────────
        emit("step_start", {"step": 1, "name": "Keyword Research"})

        keyword_result = run_keyword_research(topic, target_market, page_type=page_type)
        _save_output(keyword_result, f"{timestamp}_{slug}_keywords.json")

        emit("step_complete", {
            "step": 1,
            "preview": keyword_result["research"][:700],
            "usage": keyword_result["usage"],
        })

        # ── PASO 2: Copy ──────────────────────────────────────────────────────
        emit("step_start", {"step": 2, "name": f"Copywriting — {page_type}"})

        copy_fn = COPY_AGENTS[page_type]
        copy_result = copy_fn(keyword_result, company_context)
        _save_output(copy_result, f"{timestamp}_{slug}_copy.json")

        emit("step_complete", {
            "step": 2,
            "usage": copy_result["usage"],
        })

        # ── REVISIÓN HUMANA ───────────────────────────────────────────────────
        if not skip_upload and not skip_review:
            emit("review_needed", {
                "copy_data": copy_result.get("copy_data", {}),
                "page_type": copy_result.get("page_type", "service"),
                "topic": copy_result.get("topic", topic),
            })
            # Bloquear el thread hasta que el usuario decida en el navegador
            _jobs[job_id]["review_event"].wait()
            approved = _jobs[job_id]["review_approved"]

            if not approved:
                emit("pipeline_complete", {
                    "status": "rejected",
                    "message": "Copy rechazado. Pipeline detenido.",
                    "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json"],
                })
                return

            emit("review_approved", {"message": "Copy aprobado. Continuando con el upload…"})

        # ── PASO 3: Webflow Upload ────────────────────────────────────────────
        if skip_upload:
            emit("pipeline_complete", {
                "status": "completed_no_upload",
                "message": "Pipeline completado. Upload a Webflow omitido (skip-upload).",
                "outputs": [f"{timestamp}_{slug}_keywords.json", f"{timestamp}_{slug}_copy.json"],
            })
            return

        emit("step_start", {"step": 3, "name": "Webflow Upload"})

        webflow_result = run_webflow_upload(
            copy_result,
            site_id=site_id,
            collection_id=collection_id,
            auto_publish=auto_publish,
        )
        _save_output(webflow_result, f"{timestamp}_{slug}_webflow.json")

        emit("step_complete", {
            "step": 3,
            "result_preview": webflow_result["result"][:500],
            "usage": webflow_result["usage"],
        })

        total = {
            "keyword_research": keyword_result,
            "copywriting": copy_result,
            "webflow": webflow_result,
        }
        _save_output(total, f"{timestamp}_{slug}_COMPLETE.json")

        emit("pipeline_complete", {
            "status": "completed",
            "message": "✅ Pipeline completado exitosamente.",
            "webflow_preview": webflow_result["result"][:600],
            "outputs": [
                f"{timestamp}_{slug}_keywords.json",
                f"{timestamp}_{slug}_copy.json",
                f"{timestamp}_{slug}_webflow.json",
                f"{timestamp}_{slug}_COMPLETE.json",
            ],
        })

    except Exception as exc:
        emit("pipeline_error", {"message": str(exc)})
    finally:
        q.put(None)  # Sentinel: cierra el stream SSE


# ─── Rutas ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/jobs")
async def create_job(request: Request):
    """Inicia un nuevo job de pipeline y retorna su ID."""
    params = await request.json()

    if not params.get("topic", "").strip():
        raise HTTPException(status_code=400, detail="El campo 'topic' es requerido.")

    if params.get("page_type", "service") not in COPY_AGENTS:
        raise HTTPException(status_code=400, detail="page_type inválido.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "queue": queue.Queue(),
        "review_event": threading.Event(),
        "review_approved": False,
        "status": "running",
    }

    thread = threading.Thread(target=_run_pipeline, args=(job_id, params), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE stream de eventos del pipeline."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    async def event_generator():
        while True:
            try:
                event = _jobs[job_id]["queue"].get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.15)
                # Heartbeat para mantener la conexión
                yield ": heartbeat\n\n"
                continue

            if event is None:
                yield "event: done\ndata: {}\n\n"
                break

            payload = json.dumps(event["data"], ensure_ascii=False)
            yield f"event: {event['type']}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/jobs/{job_id}/review")
async def submit_review(job_id: str, request: Request):
    """Recibe la decisión de revisión humana (approve/reject)."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    body = await request.json()
    approved = bool(body.get("approved", False))

    _jobs[job_id]["review_approved"] = approved
    _jobs[job_id]["review_event"].set()

    return {"status": "ok", "approved": approved}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
