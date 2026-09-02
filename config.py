"""
VOV AI - Central configuration.

Everything is environment driven so you never have to edit Python
to point at a different Ollama host or swap models.
Copy .env.example to .env and edit that instead.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


# ------------------------------------------------------------------
# Ollama
# ------------------------------------------------------------------

OLLAMA_HOST = _env("OLLAMA_HOST", "http://127.0.0.1:11434")

# These are resolved against what is actually installed at runtime,
# so a typo or a missing pull degrades gracefully instead of crashing.
CHAT_MODEL = _env("VOV_CHAT_MODEL", "qwen2.5:3b")
FAST_MODEL = _env("VOV_FAST_MODEL", "qwen2.5-coder:7b")
POWERFUL_MODEL = _env("VOV_POWERFUL_MODEL", "qwen2.5-coder:14b")
VISION_MODEL = _env("VOV_VISION_MODEL", "llava:7b")

# Ordered fallbacks used when nothing configured is installed.
FALLBACK_MODELS = [
    "qwen2.5-coder:7b",
    "qwen2.5:7b",
    "qwen2.5:3b",
    "llama3.2:3b",
    "llama3.1:8b",
    "mistral:7b",
    "gemma2:9b",
    "phi3:mini",
]

# Substrings that mark a model as multimodal.
VISION_HINTS = ("llava", "vision", "bakllava", "moondream", "minicpm-v", "gemma3")

TEMPERATURE = float(_env("VOV_TEMPERATURE", "0.7"))
TOP_P = float(_env("VOV_TOP_P", "0.9"))
NUM_CTX = _env_int("VOV_NUM_CTX", 8192)

# How long the installed-model list is cached, in seconds.
MODEL_CACHE_TTL = _env_int("VOV_MODEL_CACHE_TTL", 30)


# ------------------------------------------------------------------
# Server
# ------------------------------------------------------------------

HOST = _env("VOV_HOST", "127.0.0.1")
PORT = _env_int("VOV_PORT", 8001)

# Comma separated. "*" allows everything (fine for local dev).
CORS_ORIGINS = [
    origin.strip()
    for origin in _env("VOV_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]


# ------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------

PROJECTS_DIR = Path(
    _env("VOV_PROJECTS_DIR", str(BASE_DIR / "generated_projects"))
).resolve()

DB_PATH = Path(_env("VOV_DB_PATH", str(BASE_DIR / "vov_ai.db"))).resolve()

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Limits
# ------------------------------------------------------------------

# Guards against sending a 400 file project into an 8k context window.
MAX_CONTEXT_FILES = _env_int("VOV_MAX_CONTEXT_FILES", 25)
MAX_FILE_CHARS = _env_int("VOV_MAX_FILE_CHARS", 12000)
MAX_TOTAL_CONTEXT_CHARS = _env_int("VOV_MAX_TOTAL_CONTEXT_CHARS", 60000)

# Chat turns kept when replaying history to the model.
MAX_HISTORY_TURNS = _env_int("VOV_MAX_HISTORY_TURNS", 20)

# Repair attempts in the auto fixer.
MAX_FIX_ATTEMPTS = _env_int("VOV_MAX_FIX_ATTEMPTS", 4)

# Files that are never read into model context or served.
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".cache",
}

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
    ".pdf", ".zip", ".gz", ".tar", ".mp3", ".mp4", ".wav",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".db", ".sqlite",
}
