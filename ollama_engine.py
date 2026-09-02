"""
VOV AI - Ollama engine.

Fixes over the original:
  * Model names are resolved against what is actually installed,
    so a missing pull degrades to a working model instead of a 404.
  * think=True is negotiated, not assumed (older models reject it).
  * Conversation history is supported.
  * Images (vision) are supported and auto-route to a multimodal model.
  * Every failure path returns a readable message instead of a traceback.
"""

import threading
import time
from typing import Dict, Generator, List, Optional

import ollama

import config

# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------

_client = ollama.Client(host=config.OLLAMA_HOST)

_model_cache: Dict[str, object] = {"at": 0.0, "models": []}
_cache_lock = threading.Lock()

# Models known to reject the `think` parameter, learned at runtime.
_no_think: set = set()


# ------------------------------------------------------------------
# System prompt
# ------------------------------------------------------------------

SYSTEM_PROMPT = """You are VOV AI, a local AI assistant and software development agent
running through Ollama.

You help users:
- answer questions and explain concepts
- write, debug and fix code
- build complete websites and applications
- modify and improve existing projects

Rules:
1. Understand the request before answering. Be direct and useful.
2. When the user names a language or framework, always use it.
3. If none is named, choose the most suitable option yourself.
4. For plain websites use HTML, CSS and JavaScript unless told otherwise.
5. When modifying a project, preserve existing functionality and design
   unless the user explicitly asks you to change it.
6. Never write placeholders such as TODO, YOUR CODE HERE, or ADD CODE HERE.
   Write complete, working code.
7. Never invent fake functionality or dead buttons.
8. Format code in fenced markdown blocks with a language tag.
9. Do not expose hidden reasoning. Keep any progress notes short.
"""


# ------------------------------------------------------------------
# Routing keywords
# ------------------------------------------------------------------

CODING_KEYWORDS = [
    "code", "coding", "program", "programming", "script",
    "website", "web app", "web application", "application", "app",
    "software", "python", "javascript", "typescript", "react",
    "reactjs", "nextjs", "next.js", "vue", "svelte", "html", "css",
    "tailwind", "api", "backend", "frontend", "fastapi", "flask",
    "django", "express", "node", "nodejs", "database", "sql",
    "sqlite", "postgres", "mongodb", "debug", "debugging", "bug",
    "error", "exception", "traceback", "fix", "refactor", "build",
    "create", "develop", "deploy", "project", "component",
    "function", "class", "algorithm", "regex", "git", "github",
    "docker", "test", "unit test",
]

COMPLEX_KEYWORDS = [
    "full stack", "full-stack", "complete application", "complete app",
    "complete website", "build an app", "build a website",
    "build application", "generate project", "create project",
    "large project", "complex project", "architecture", "microservice",
    "authentication", "authorization", "database", "api integration",
    "backend", "frontend", "dashboard", "admin panel", "ecommerce",
    "e-commerce", "login system", "signup system", "payment",
    "real time", "realtime", "websocket", "multi page", "multipage",
]


def is_coding_request(prompt: str) -> bool:
    text = str(prompt).lower()
    return any(word in text for word in CODING_KEYWORDS)


def is_complex_request(prompt: str) -> bool:
    text = str(prompt).lower()
    return any(word in text for word in COMPLEX_KEYWORDS)


# ------------------------------------------------------------------
# Installed models
# ------------------------------------------------------------------

def installed_models(force: bool = False) -> List[str]:
    """Names of every model installed in Ollama. Cached briefly."""

    with _cache_lock:
        fresh = (time.time() - float(_model_cache["at"])) < config.MODEL_CACHE_TTL

        if not force and fresh and _model_cache["models"]:
            return list(_model_cache["models"])  # type: ignore[arg-type]

    names: List[str] = []

    try:
        result = _client.list()

        # ollama-python changed its return shape between versions,
        # so handle both the object form and the dict form.
        raw = getattr(result, "models", None)

        if raw is None and isinstance(result, dict):
            raw = result.get("models", [])

        for item in raw or []:
            name = (
                getattr(item, "model", None)
                or getattr(item, "name", None)
                or (item.get("model") or item.get("name") if isinstance(item, dict) else None)
            )

            if name:
                names.append(str(name))

        names = list(dict.fromkeys(names))

    except Exception as error:  # Ollama down, wrong host, etc.
        print(f"[vov] could not list Ollama models: {error}")
        names = []

    with _cache_lock:
        _model_cache["at"] = time.time()

        if names:
            _model_cache["models"] = names

    return names


def is_online() -> bool:
    try:
        _client.list()
        return True
    except Exception:
        return False


def is_vision_model(name: str) -> bool:
    lowered = (name or "").lower()
    return any(hint in lowered for hint in config.VISION_HINTS)


def _match(wanted: str, available: List[str]) -> Optional[str]:
    """Best-effort match of a wanted model against installed ones."""

    if not wanted:
        return None

    wanted = wanted.strip()
    lowered = wanted.lower()

    for name in available:
        if name.lower() == lowered:
            return name

    # "qwen2.5-coder" should match "qwen2.5-coder:7b"
    for name in available:
        if name.lower().split(":")[0] == lowered.split(":")[0]:
            return name

    for name in available:
        if lowered in name.lower():
            return name

    return None


def resolve_model(wanted: str, prefer_vision: bool = False) -> str:
    """
    Turn a requested model name into one that actually exists.

    Falls back through the configured defaults and then through
    config.FALLBACK_MODELS. Raises only when Ollama has nothing at all.
    """

    available = installed_models()

    if not available:
        raise RuntimeError(
            "No models are installed in Ollama. "
            "Run `ollama pull qwen2.5:3b` and try again."
        )

    if prefer_vision:
        match = _match(config.VISION_MODEL, available)

        if match:
            return match

        for name in available:
            if is_vision_model(name):
                return name

        # No multimodal model installed; caller drops the images.

    match = _match(wanted, available)

    if match:
        return match

    for candidate in (
        config.FAST_MODEL,
        config.CHAT_MODEL,
        config.POWERFUL_MODEL,
        *config.FALLBACK_MODELS,
    ):
        match = _match(candidate, available)

        if match:
            return match

    return available[0]


def select_model(
    prompt: str,
    requested_model: str = "auto",
    has_images: bool = False,
) -> str:
    """Pick a model for this prompt, honouring an explicit choice."""

    requested = (requested_model or "auto").lower().strip()

    if has_images:
        return resolve_model(
            requested if requested != "auto" else config.VISION_MODEL,
            prefer_vision=True,
        )

    if requested != "auto":
        return resolve_model(requested)

    if is_complex_request(prompt):
        return resolve_model(config.POWERFUL_MODEL)

    if is_coding_request(prompt):
        return resolve_model(config.FAST_MODEL)

    return resolve_model(config.CHAT_MODEL)


def get_available_models() -> dict:
    available = installed_models()

    return {
        "auto": True,
        "online": bool(available),
        "installed": available,
        "vision": [name for name in available if is_vision_model(name)],
        "chat": config.CHAT_MODEL,
        "fast": config.FAST_MODEL,
        "powerful": config.POWERFUL_MODEL,
        "vision_default": config.VISION_MODEL,
        "host": config.OLLAMA_HOST,
    }


# ------------------------------------------------------------------
# Message building
# ------------------------------------------------------------------

def build_messages(
    prompt: str,
    history: Optional[List[dict]] = None,
    images: Optional[List[str]] = None,
    system: Optional[str] = None,
) -> List[dict]:
    messages: List[dict] = [
        {"role": "system", "content": system or SYSTEM_PROMPT}
    ]

    for turn in (history or [])[-config.MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = turn.get("content")

        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)})

    user_message: dict = {"role": "user", "content": prompt}

    if images:
        # Ollama wants raw base64 without the data-url prefix.
        cleaned = []

        for image in images:
            if not image:
                continue

            if "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]

            cleaned.append(image.strip())

        if cleaned:
            user_message["images"] = cleaned

    messages.append(user_message)

    return messages


def _options() -> dict:
    return {
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "num_ctx": config.NUM_CTX,
    }


def _friendly_error(error: Exception) -> str:
    text = str(error)

    if "connection" in text.lower() or "refused" in text.lower():
        return (
            f"Cannot reach Ollama at {config.OLLAMA_HOST}. "
            "Start it with `ollama serve` and try again."
        )

    if "not found" in text.lower() and "model" in text.lower():
        return f"{text}. Pull it first with `ollama pull <model>`."

    return text


# ------------------------------------------------------------------
# Blocking call
# ------------------------------------------------------------------

def ask_model(
    prompt: str,
    model: str = "auto",
    history: Optional[List[dict]] = None,
    images: Optional[List[str]] = None,
    system: Optional[str] = None,
    return_model: bool = False,
):
    selected = select_model(prompt, model, has_images=bool(images))

    if images and not is_vision_model(selected):
        images = None  # No multimodal model available; send text only.

    messages = build_messages(prompt, history, images, system)

    try:
        response = _client.chat(
            model=selected,
            messages=messages,
            options=_options(),
        )

    except Exception as error:
        raise RuntimeError(_friendly_error(error)) from error

    message = getattr(response, "message", None)

    if message is None and isinstance(response, dict):
        message = response.get("message", {})

    answer = (
        getattr(message, "content", None)
        or (message.get("content") if isinstance(message, dict) else None)
        or ""
    )

    if return_model:
        return {"response": answer, "model": selected}

    return answer


# ------------------------------------------------------------------
# Streaming call
# ------------------------------------------------------------------

def _start_stream(model: str, messages: List[dict], think: bool):
    kwargs = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": _options(),
    }

    if think:
        kwargs["think"] = True

    return _client.chat(**kwargs)


def stream_model(
    prompt: str,
    model: str = "auto",
    history: Optional[List[dict]] = None,
    images: Optional[List[str]] = None,
    system: Optional[str] = None,
    should_stop=None,
) -> Generator[dict, None, None]:
    """
    Yield {"type": thinking|content|done|error, "content": str, "model": str}.

    `should_stop` is an optional callable checked between chunks so the
    HTTP layer can abort a runaway generation.
    """

    try:
        selected = select_model(prompt, model, has_images=bool(images))

    except Exception as error:
        yield {"type": "error", "content": _friendly_error(error), "model": model}
        yield {"type": "done", "content": "", "model": model}
        return

    if images and not is_vision_model(selected):
        images = None

    messages = build_messages(prompt, history, images, system)

    want_think = selected not in _no_think

    try:
        try:
            stream = _start_stream(selected, messages, want_think)

        except TypeError:
            # Installed ollama-python predates the `think` argument.
            _no_think.add(selected)
            stream = _start_stream(selected, messages, False)

        except Exception as error:
            if want_think and "think" in str(error).lower():
                _no_think.add(selected)
                stream = _start_stream(selected, messages, False)
            else:
                raise

        for chunk in stream:
            if should_stop and should_stop():
                yield {"type": "stopped", "content": "", "model": selected}
                break

            message = getattr(chunk, "message", None)

            if message is None and isinstance(chunk, dict):
                message = chunk.get("message", {})

            if message is None:
                continue

            if isinstance(message, dict):
                thinking = message.get("thinking")
                content = message.get("content")
            else:
                thinking = getattr(message, "thinking", None)
                content = getattr(message, "content", None)

            if thinking:
                yield {"type": "thinking", "content": thinking, "model": selected}

            if content:
                yield {"type": "content", "content": content, "model": selected}

    except Exception as error:
        yield {"type": "error", "content": _friendly_error(error), "model": selected}

    yield {"type": "done", "content": "", "model": selected}
