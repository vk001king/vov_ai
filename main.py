from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from ollama_engine import (
    ask_model,
    stream_model,
    get_available_models
)

from project_generator import generate_project
from project_tester import test_project
from project_fixer import fix_project
from build_status import get_status
from project_manager import read_project


# ============================================================
# VOV AI
# ============================================================

app = FastAPI(
    title="VOV AI",
    description="Local AI-powered application and website builder",
    version="1.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "auto"


class ProjectRequest(BaseModel):
    project_name: str
    request: str
    model: Optional[str] = "auto"

    # auto / create / modify
    mode: Optional[str] = "auto"


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "name": "VOV AI",
        "status": "online",
        "model": "auto"
    }


# ============================================================
# AVAILABLE MODELS
# ============================================================

@app.get("/models")
def models():

    data = get_available_models()

    return {
        "models": data.get("installed", [])
    }


# ============================================================
# PROJECT FILES
# ============================================================

@app.get("/project/{project_name}")
def project_files(project_name: str):

    files = read_project(project_name)

    return {
        "project": project_name,

        "files": [
            {
                "name": filename,
                "content": content
            }

            for filename, content
            in files.items()
        ]
    }


# ============================================================
# NORMAL CHAT
# ============================================================

@app.post("/chat")
def chat(request: ChatRequest):

    result = ask_model(
        prompt=request.message,
        model=request.model,
        return_model=True
    )

    return result


# ============================================================
# STREAMING CHAT
# ============================================================

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):

    def generate():

        try:

            for chunk in stream_model(
                prompt=request.message,
                model=request.model
            ):

                yield (
                    json.dumps(
                        chunk,
                        ensure_ascii=False
                    )
                    + "\n"
                )

        except Exception as e:

            yield (
                json.dumps(
                    {
                        "type": "error",
                        "content": str(e)
                    },
                    ensure_ascii=False
                )
                + "\n"
            )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )


# ============================================================
# GENERATE / MODIFY PROJECT
# ============================================================

@app.post("/generate")
def generate(
    request: ProjectRequest,
    background_tasks: BackgroundTasks
):

    # --------------------------------------------------------
    # NORMALIZE MODE
    # --------------------------------------------------------

    mode = (
        request.mode or "auto"
    ).lower().strip()


    # --------------------------------------------------------
    # VALID MODES
    # --------------------------------------------------------

    if mode not in [
        "auto",
        "create",
        "modify"
    ]:

        mode = "auto"


    # --------------------------------------------------------
    # START BACKGROUND BUILD
    # --------------------------------------------------------

    background_tasks.add_task(
        generate_project,

        request.project_name,

        request.request,

        request.model,

        mode
    )


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {

        "message": "Project operation started",

        "project": request.project_name,

        "model": request.model,

        "mode": mode,

        "working": True
    }


# ============================================================
# TEST PROJECT
# ============================================================

@app.post("/test/{project_name}")
def test_existing_project(
    project_name: str
):

    errors = test_project(
        project_name
    )

    return {

        "project": project_name,

        "working": len(errors) == 0,

        "errors": errors
    }


# ============================================================
# FIX PROJECT
# ============================================================

@app.post("/fix/{project_name}")
def fix_existing_project(
    project_name: str
):

    result = fix_project(
        project_name
    )

    return {

        "project": project_name,

        **result
    }


# ============================================================
# BUILD STATUS
# ============================================================

@app.get("/status/{project_name}")
def project_status(
    project_name: str
):

    return get_status(
        project_name
    )

