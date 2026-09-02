"""
VOV AI - Project generation and modification.

Improvements over the original:
  * File parsing tolerates markdown fences and several common formats
    the model drifts into, instead of failing outright.
  * One automatic reformat retry when the first response is unparseable.
  * The generated project is validated, and optionally auto repaired.
  * Cancellation is honoured between files.
  * Project context is length capped so large projects still work.
"""

import re
from typing import List, Optional

import config
from build_status import (
    add_error,
    cancel_requested,
    file_completed,
    finish_build,
    log,
    set_model,
    start_build,
    update_status,
)
from ollama_engine import ask_model, select_model
from project_manager import (
    create_file,
    create_project,
    get_project_context,
    project_exists,
    read_project,
)
from project_tester import test_project

BASE_DIR = config.PROJECTS_DIR


# ==================================================================
# Response parsing
# ==================================================================

_FILE_BLOCK = re.compile(
    r"===\s*FILE:\s*(?P<name>.+?)\s*===\s*\n(?P<body>.*?)(?:\n\s*===\s*END\s*FILE\s*===|\Z)",
    re.DOTALL | re.IGNORECASE,
)

_FENCE_WITH_NAME = re.compile(
    r"(?:^|\n)(?:#{1,4}\s*)?(?:File:\s*)?[`*\s]*(?P<name>[\w./-]+\.[a-zA-Z0-9]{1,5})[`*\s]*:?\s*\n+"
    r"```[a-zA-Z0-9+#-]*\s*\n(?P<body>.*?)```",
    re.DOTALL,
)


def _strip_fences(text: str) -> str:
    text = text.strip()

    match = re.match(r"^```[a-zA-Z0-9+#-]*\s*\n(.*?)\n?```$", text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return text


def _clean_name(name: str) -> str:
    name = name.strip().strip("`*\"' ")
    name = name.replace("\\", "/").lstrip("/")
    name = re.sub(r"^(?:file|filename|path)\s*[:=]\s*", "", name, flags=re.IGNORECASE)

    return name.strip()


def extract_files(response: str) -> List[dict]:
    """
    Pull files out of a model response.

    Primary format:
        ===FILE: index.html===
        ...
        ===END FILE===

    Falls back to fenced code blocks preceded by a filename, which is
    what smaller models tend to produce when they forget the format.
    """

    files: List[dict] = []
    seen: set = set()

    for match in _FILE_BLOCK.finditer(response or ""):
        name = _clean_name(match.group("name"))
        body = _strip_fences(match.group("body"))

        if name and body and name not in seen:
            seen.add(name)
            files.append({"name": name, "content": body})

    if files:
        return files

    for match in _FENCE_WITH_NAME.finditer(response or ""):
        name = _clean_name(match.group("name"))
        body = match.group("body").strip()

        if name and body and name not in seen:
            seen.add(name)
            files.append({"name": name, "content": body})

    return files


# ==================================================================
# Request analysis
# ==================================================================

LANGUAGE_PATTERNS = [
    ("react", r"\breact(?:js|\.js)?\b"),
    ("typescript", r"\btypescript\b|\bts\b"),
    ("python", r"\bpython\b|\bflask\b|\bdjango\b|\bfastapi\b"),
    ("node", r"\bnode(?:js|\.js)?\b|\bexpress\b"),
    ("java", r"\bjava\b(?!script)"),
    ("c++", r"\bc\+\+\b|\bcpp\b"),
    ("c#", r"\bc#\b|\bcsharp\b|\bdotnet\b"),
    ("php", r"\bphp\b|\blaravel\b"),
    ("javascript", r"\bjavascript\b|\bvanilla js\b|\bjs\b"),
    ("html", r"\bhtml\b|\bcss\b|\bstatic site\b"),
]


def detect_language(request: str) -> str:
    text = (request or "").lower()

    for language, pattern in LANGUAGE_PATTERNS:
        if re.search(pattern, text):
            return language

    return "auto"


def detect_project_type(request: str) -> str:
    text = (request or "").lower()

    if "react" in text:
        return "React application"

    if "api" in text or "backend" in text:
        return "backend service"

    if "game" in text:
        return "browser game"

    if "dashboard" in text:
        return "dashboard"

    if "website" in text or "landing page" in text or "portfolio" in text:
        return "website"

    if "web app" in text:
        return "web application"

    if "python" in text:
        return "Python application"

    if "application" in text or " app" in text:
        return "application"

    return "software project"


MODIFICATION_WORDS = [
    "change", "modify", "update", "edit", "add ", "remove", "delete",
    "replace", "improve", "fix", "redesign", "adjust", "rename",
    "include", "make it", "make the", "instead of", "also ",
    "convert", "refactor", "enhance", "extend",
]


def is_modification_request(request: str) -> bool:
    text = (request or "").lower()

    return any(word in text for word in MODIFICATION_WORDS)


# ==================================================================
# Prompt
# ==================================================================

OUTPUT_CONTRACT = """
============================================================
OUTPUT FORMAT - THIS IS MANDATORY
============================================================

Return ONLY project files, each wrapped exactly like this:

===FILE: index.html===
<complete file contents>
===END FILE===

===FILE: style.css===
<complete file contents>
===END FILE===

Rules for the output:

- No explanations before or after the files.
- No markdown code fences.
- No JSON wrapper.
- No partial files or diffs. Every file must be complete.
- Use forward slashes in paths, relative to the project root.
- Never use absolute paths or "..".
"""


def build_generation_prompt(
    user_request: str,
    selected_model: str,
    project_name: str,
    existing_context: Optional[str] = None,
) -> str:
    language = detect_language(user_request)
    project_type = detect_project_type(user_request)

    if language != "auto":
        language_instruction = (
            f"The user explicitly asked for {language}. You MUST use it. "
            "Do not substitute another language or framework."
        )
    else:
        language_instruction = (
            "The user did not name a language. Choose the most suitable one "
            "for the request, favouring simplicity and something that runs "
            "in a browser with no build step unless the request demands more."
        )

    if existing_context:
        project_section = f"""
============================================================
EXISTING PROJECT - MODIFY IT
============================================================

This project already exists. The user wants changes made to it.

Read the files below carefully, then:

- Preserve every existing feature unless asked to remove it.
- Preserve the existing design unless asked to change it.
- Change only what the request requires.
- Return the COMPLETE contents of every file you touch.
- Do not return files you did not change.
- Keep every reference valid: each src, href and import must resolve.

Current files:

{existing_context}
"""
    else:
        project_section = """
============================================================
NEW PROJECT
============================================================

This is a brand new project. Build it completely from scratch.

For a website, produce at minimum index.html, style.css and script.js,
each linked correctly from the HTML.
"""

    return f"""You are VOV AI, an autonomous software development agent.
You create and modify complete, working software projects.

============================================================
PROJECT
============================================================

Name: {project_name}
Type: {project_type}
Model: {selected_model}

============================================================
USER REQUEST
============================================================

{user_request}

============================================================
LANGUAGE
============================================================

{language_instruction}

{project_section}

============================================================
QUALITY REQUIREMENTS
============================================================

- Every feature you claim to build must actually work.
- No dead buttons, fake forms, or simulated behaviour.
- No placeholders: no TODO, YOUR CODE HERE, ADD CODE HERE, or "...".
- Handle errors and empty states.
- Interfaces must be modern, responsive and keyboard accessible.
- Use semantic HTML and meaningful names.
- Include a <title>, a viewport meta tag, and sensible defaults.

{OUTPUT_CONTRACT}
"""


REFORMAT_PROMPT = """Your previous answer was not in the required format,
so none of it could be saved.

Return the SAME project again, changing nothing about the code itself,
but wrapping every file exactly like this:

===FILE: path/name.ext===
<complete file contents>
===END FILE===

No explanations. No markdown fences. Files only.

Your previous answer was:

{previous}
"""


# ==================================================================
# Generation
# ==================================================================

def _write_files(project_name: str, files: List[dict]) -> List[str]:
    created: List[str] = []
    total = max(len(files), 1)

    for index, item in enumerate(files, start=1):
        if cancel_requested(project_name):
            break

        filename = _clean_name(item["name"])
        content = item["content"]

        if not filename:
            continue

        progress = 40 + int((index / total) * 45)

        update_status(
            project_name,
            "writing",
            f"Writing {filename}...",
            filename,
            progress,
        )

        try:
            create_file(project_name, filename, content)
        except ValueError as error:
            add_error(project_name, str(error))
            continue

        file_completed(project_name, filename)
        created.append(filename)

    return created


def generate_project(
    project_name: str,
    user_request: str,
    requested_model: str = "auto",
    mode: str = "auto",
    auto_fix: bool = True,
) -> dict:
    """Build or modify a project. Runs in a background thread."""

    start_build(project_name, model=requested_model, mode=mode)

    update_status(project_name, "thinking", "Understanding your request...", progress=5)

    try:
        mode = (mode or "auto").lower().strip()

        if mode not in ("auto", "create", "modify"):
            mode = "auto"

        existing = read_project(project_name) if project_exists(project_name) else {}

        if mode == "create":
            modifying = False
        elif mode == "modify":
            modifying = bool(existing)
        else:
            modifying = bool(existing) and is_modification_request(user_request)

        # ----------------------------------------------------------
        # Model
        # ----------------------------------------------------------

        update_status(project_name, "planning", "Selecting a model...", progress=10)

        selected_model = select_model(user_request, requested_model)
        set_model(project_name, selected_model)

        update_status(
            project_name,
            "planning",
            f"Using {selected_model} to {'modify' if modifying else 'create'} {project_name}.",
            progress=15,
        )

        if modifying:
            update_status(
                project_name,
                "reading",
                f"Reading {len(existing)} existing file(s)...",
                progress=20,
            )

        context = get_project_context(project_name) if modifying else None

        prompt = build_generation_prompt(
            user_request,
            selected_model,
            project_name,
            context,
        )

        if cancel_requested(project_name):
            finish_build(project_name, False, "Build cancelled.")
            return {"project": project_name, "success": False, "error": "cancelled"}

        # ----------------------------------------------------------
        # Generate
        # ----------------------------------------------------------

        update_status(
            project_name,
            "generating",
            f"{selected_model} is writing code. This can take a while on a local model...",
            progress=30,
        )

        response = ask_model(prompt, selected_model)

        files = extract_files(response)

        # One retry if the model ignored the output contract.
        if not files:
            log(project_name, "Response was not in the expected format. Asking for a reformat...")

            update_status(
                project_name,
                "generating",
                "Reformatting the model's answer...",
                progress=35,
            )

            retry = ask_model(
                REFORMAT_PROMPT.format(previous=response[:12000]),
                selected_model,
            )

            files = extract_files(retry)

        if not files:
            raise ValueError(
                "The model did not return any files in a recognisable format. "
                "Try a larger model, or rephrase the request."
            )

        # ----------------------------------------------------------
        # Write
        # ----------------------------------------------------------

        create_project(project_name)

        update_status(
            project_name,
            "writing",
            f"Saving {len(files)} file(s)...",
            progress=40,
        )

        created = _write_files(project_name, files)

        if cancel_requested(project_name):
            finish_build(project_name, False, "Build cancelled after partial write.")
            return {"project": project_name, "files": created, "success": False, "error": "cancelled"}

        if not created:
            raise ValueError("No valid project files could be written.")

        # ----------------------------------------------------------
        # Validate
        # ----------------------------------------------------------

        update_status(project_name, "testing", "Checking the generated project...", progress=90)

        errors = test_project(project_name)

        if errors and auto_fix:
            update_status(
                project_name,
                "fixing",
                f"Found {len(errors)} issue(s). Attempting automatic repair...",
                progress=93,
            )

            from project_fixer import fix_project  # Imported late to avoid a cycle.

            result = fix_project(project_name, model=selected_model)

            errors = result.get("errors", []) if not result.get("working") else []

            for name in result.get("fixed_files", []):
                if name not in created:
                    created.append(name)

        for error in errors:
            add_error(project_name, error)

        if errors:
            finish_build(
                project_name,
                success=True,
                message=f"Project built with {len(errors)} remaining warning(s).",
            )
        else:
            finish_build(
                project_name,
                success=True,
                message="Project modified successfully." if modifying else "Project generated successfully.",
            )

        return {
            "project": project_name,
            "files": created,
            "model": selected_model,
            "language": detect_language(user_request),
            "modified": modifying,
            "mode": "modify" if modifying else "create",
            "warnings": errors,
            "success": True,
        }

    except Exception as error:  # noqa: BLE001 - surfaced to the user
        message = str(error)

        add_error(project_name, message)
        finish_build(project_name, success=False, message=f"Build failed: {message}")

        return {
            "project": project_name,
            "files": [],
            "model": requested_model,
            "success": False,
            "error": message,
        }
