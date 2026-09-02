"""
VOV AI - FastAPI application.

Run with:
    python main.py
or:
    uvicorn main:app --reload --port 8001
"""

import json
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import build_status
import config
import ollama_engine
import store
from ollama_engine import ask_model, get_available_models, stream_model
from project_fixer import fix_project
from project_generator import generate_project
from project_manager import (
    create_file,
    delete_file,
    delete_project,
    is_valid_project_name,
    list_project_files,
    list_projects,
    project_exists,
    read_project,
    rename_project,
    zip_project,
)
from project_tester import project_report

store.init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.init_db()

    print(f"[vov] projects dir : {config.PROJECTS_DIR}")
    print(f"[vov] ollama host  : {config.OLLAMA_HOST}")

    found = ollama_engine.installed_models(force=True)

    if found:
        print(f"[vov] models found : {', '.join(found)}")
    else:
        print("[vov] WARNING: Ollama is unreachable or has no models installed.")
        print("[vov] Start it with `ollama serve` and pull a model, e.g.")
        print("[vov]   ollama pull qwen2.5:3b")

    yield


app = FastAPI(
    title="VOV AI",
    description="Local AI-powered application and website builder",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generated projects are served straight from disk so the frontend can
# show a live preview in an iframe.
app.mount(
    "/preview",
    StaticFiles(directory=str(config.PROJECTS_DIR), html=True),
    name="preview",
)


# ==================================================================
# Models
# ==================================================================

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: Optional[str] = "auto"
    session_id: Optional[str] = None
    images: Optional[List[str]] = None
    system: Optional[str] = None
    remember: bool = True


class ProjectRequest(BaseModel):
    project_name: str
    request: str = Field(min_length=1)
    model: Optional[str] = "auto"
    mode: Optional[str] = "auto"
    auto_fix: bool = True


class FileRequest(BaseModel):
    path: str
    content: str


class RenameRequest(BaseModel):
    title: str


# ==================================================================
# System
# ==================================================================

@app.get("/")
def home():
    return {
        "name": "VOV AI",
        "version": "2.0",
        "status": "online",
        "ollama": ollama_engine.is_online(),
        "host": config.OLLAMA_HOST,
    }


@app.get("/health")
def health():
    models = ollama_engine.installed_models()

    return {
        "api": "ok",
        "ollama": bool(models),
        "model_count": len(models),
        "projects": len(list_projects()),
    }


@app.get("/models")
def models(refresh: bool = False):
    if refresh:
        ollama_engine.installed_models(force=True)

    data = get_available_models()

    # Kept flat for backwards compatibility with the old frontend.
    return {"models": data["installed"], **data}


# ==================================================================
# Chat sessions
# ==================================================================

@app.get("/sessions")
def sessions():
    return {"sessions": store.list_sessions()}


@app.post("/sessions")
def new_session():
    return store.create_session()


@app.get("/sessions/{session_id}")
def session_detail(session_id: str):
    if not store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")

    return {"id": session_id, "messages": store.get_messages(session_id)}


@app.patch("/sessions/{session_id}")
def rename(session_id: str, body: RenameRequest):
    if not store.rename_session(session_id, body.title):
        raise HTTPException(404, "Session not found.")

    return {"id": session_id, "title": body.title}


@app.delete("/sessions/{session_id}")
def remove_session(session_id: str):
    return {"deleted": store.delete_session(session_id)}


@app.delete("/sessions")
def clear_sessions():
    return {"deleted": store.clear_all_sessions()}


# ==================================================================
# Chat
# ==================================================================

def _prepare_session(body: ChatRequest) -> Optional[str]:
    if not body.remember:
        return None

    session_id = body.session_id

    if not session_id or not store.session_exists(session_id):
        session_id = store.create_session()["id"]

    return session_id


@app.post("/chat")
def chat(body: ChatRequest):
    session_id = _prepare_session(body)

    history = store.get_history_for_model(session_id) if session_id else []

    try:
        result = ask_model(
            prompt=body.message,
            model=body.model or "auto",
            history=history,
            images=body.images,
            system=body.system,
            return_model=True,
        )

    except Exception as error:  # noqa: BLE001
        raise HTTPException(503, str(error)) from error

    if session_id:
        store.append_message(session_id, "user", body.message, images=body.images)
        store.append_message(session_id, "assistant", result["response"], model=result["model"])
        store.autotitle_session(session_id, body.message)

    return {**result, "session_id": session_id}


@app.post("/chat/stream")
def chat_stream(body: ChatRequest):
    """Newline-delimited JSON stream: {type, content, model}."""

    session_id = _prepare_session(body)

    history = store.get_history_for_model(session_id) if session_id else []

    def generate():
        collected: List[str] = []
        used_model = body.model or "auto"

        if session_id:
            yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

        try:
            for chunk in stream_model(
                prompt=body.message,
                model=body.model or "auto",
                history=history,
                images=body.images,
                system=body.system,
            ):
                if chunk.get("type") == "content":
                    collected.append(chunk["content"])

                if chunk.get("model"):
                    used_model = chunk["model"]

                yield json.dumps(chunk, ensure_ascii=False) + "\n"

        except Exception as error:  # noqa: BLE001
            yield json.dumps({"type": "error", "content": str(error)}, ensure_ascii=False) + "\n"

        answer = "".join(collected).strip()

        if session_id and answer:
            store.append_message(session_id, "user", body.message, images=body.images)
            store.append_message(session_id, "assistant", answer, model=used_model)
            store.autotitle_session(session_id, body.message)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ==================================================================
# Projects
# ==================================================================

@app.get("/projects")
def projects():
    return {"projects": list_projects()}


@app.get("/project/{project_name}")
def project_files(project_name: str):
    if not is_valid_project_name(project_name):
        raise HTTPException(400, "Invalid project name.")

    if not project_exists(project_name):
        raise HTTPException(404, "Project not found.")

    files = read_project(project_name)

    return {
        "project": project_name,
        "files": [{"name": name, "content": content} for name, content in files.items()],
        "index": list_project_files(project_name),
        "preview_url": f"/preview/{project_name}/index.html",
    }


@app.put("/project/{project_name}/file")
def write_project_file(project_name: str, body: FileRequest):
    if not project_exists(project_name):
        raise HTTPException(404, "Project not found.")

    try:
        create_file(project_name, body.path, body.content)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    return {"project": project_name, "path": body.path, "saved": True}


@app.delete("/project/{project_name}/file")
def remove_project_file(project_name: str, path: str):
    if not project_exists(project_name):
        raise HTTPException(404, "Project not found.")

    try:
        deleted = delete_file(project_name, path)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error

    return {"deleted": deleted}


@app.delete("/project/{project_name}")
def remove_project(project_name: str):
    if build_status.is_running(project_name):
        raise HTTPException(409, "A build is currently running for this project.")

    return {"deleted": delete_project(project_name)}


@app.post("/project/{project_name}/rename")
def move_project(project_name: str, body: RenameRequest):
    if not is_valid_project_name(body.title):
        raise HTTPException(400, "Invalid new project name.")

    if not rename_project(project_name, body.title):
        raise HTTPException(400, "Rename failed. The target name may already exist.")

    return {"project": body.title}


@app.get("/download/{project_name}")
def download_project(project_name: str):
    if not is_valid_project_name(project_name):
        raise HTTPException(400, "Invalid project name.")

    buffer = zip_project(project_name)

    if buffer is None:
        raise HTTPException(404, "Project not found.")

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_name}.zip"'},
    )


# ==================================================================
# Build
# ==================================================================

@app.post("/generate")
def generate(body: ProjectRequest, background_tasks: BackgroundTasks):
    if not is_valid_project_name(body.project_name):
        raise HTTPException(
            400,
            "Project names may contain letters, numbers, dots, dashes and underscores only.",
        )

    if build_status.is_running(body.project_name):
        raise HTTPException(409, "A build is already running for this project.")

    mode = (body.mode or "auto").lower().strip()

    if mode not in ("auto", "create", "modify"):
        mode = "auto"

    # Registered up front so the first status poll never 404s.
    build_status.start_build(body.project_name, model=body.model, mode=mode)

    background_tasks.add_task(
        generate_project,
        body.project_name,
        body.request,
        body.model or "auto",
        mode,
        body.auto_fix,
    )

    return {
        "message": "Build started.",
        "project": body.project_name,
        "model": body.model,
        "mode": mode,
        "working": True,
    }


@app.get("/status/{project_name}")
def project_status(project_name: str):
    return build_status.get_status(project_name)


@app.get("/status")
def all_status():
    return {"builds": build_status.list_builds()}


@app.post("/cancel/{project_name}")
def cancel_build(project_name: str):
    return {"cancelled": build_status.request_cancel(project_name)}


@app.get("/status/{project_name}/stream")
def status_stream(project_name: str):
    """Server-sent-style stream of build status until the build ends."""

    import time

    def generate():
        last = None

        for _ in range(1800):  # ~15 minutes at 0.5s
            current = build_status.get_status(project_name)

            payload = json.dumps(current, ensure_ascii=False)

            if payload != last:
                yield payload + "\n"
                last = payload

            if current.get("finished"):
                break

            time.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/test/{project_name}")
def test_existing_project(project_name: str):
    if not project_exists(project_name):
        raise HTTPException(404, "Project not found.")

    return project_report(project_name)


@app.post("/fix/{project_name}")
def fix_existing_project(project_name: str, model: str = "auto"):
    if not project_exists(project_name):
        raise HTTPException(404, "Project not found.")

    result = fix_project(project_name, model=None if model == "auto" else model)

    return {"project": project_name, **result}


# ==================================================================
# Entry point
# ==================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
