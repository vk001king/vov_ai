from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks
from ollama_engine import ask_model
from project_generator import generate_project
from project_tester import test_project
from project_fixer import fix_project
from build_status import get_status


app = FastAPI(
    title="VOV AI",
    description="Local AI-powered application and website builder",
    version="1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# REQUEST MODELS
# ==========================================

class ChatRequest(BaseModel):
    message: str


class ProjectRequest(BaseModel):
    project_name: str
    request: str


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():

    return {
        "name": "VOV AI",
        "status": "online",
        "model": "qwen3.5-4b"
    }


# ==========================================
# CHAT
# ==========================================

@app.post("/chat")
def chat(request: ChatRequest):

    response = ask_model(
        request.message
    )

    return {
        "response": response
    }


# ==========================================
# GENERATE PROJECT
# ==========================================

@app.post("/generate")
def generate(request: ProjectRequest):

    project = generate_project(
        request.project_name,
        request.request
    )

    errors = test_project(
        request.project_name
    )

    return {
        "message": "Project generated successfully",
        "project": project,
        "working": len(errors) == 0,
        "errors": errors
    }


# ==========================================
# TEST PROJECT
# ==========================================

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


# ==========================================
# FIX PROJECT
# ==========================================

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
# ==========================================
# BUILD STATUS
# ==========================================

@app.get("/status/{project_name}")
def project_status(project_name: str):

    return get_status(project_name)
@app.post("/generate")
def generate(request: ProjectRequest, background_tasks: BackgroundTasks):

    background_tasks.add_task(
        generate_project,
        request.project_name,
        request.request
    )

    return {
        "message": "Project generation started",
        "project": request.project_name,
        "working": True
    }