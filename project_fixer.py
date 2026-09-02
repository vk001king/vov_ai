"""
VOV AI - Automatic project repair.

Improvements over the original:
  * The model is shown the current contents of the broken file, not just
    the error string, so it can actually repair rather than guess.
  * Writes go through the same safe-path helper as everything else.
  * Progress is reported to the build status tracker.
  * It stops early when an attempt makes no difference.
"""

import re
from typing import List, Optional

import config
from build_status import log, update_status
from ollama_engine import ask_model, resolve_model
from project_manager import create_file, project_exists, read_file, read_project
from project_tester import test_project

FILE_PATTERN = re.compile(r"FILE:\s*(?P<name>[^\n`*\"']+)", re.IGNORECASE)
CONTENT_PATTERN = re.compile(r"CONTENT:\s*\n?(?P<body>.*)", re.IGNORECASE | re.DOTALL)


def _strip_fences(text: str) -> str:
    text = text.strip()

    match = re.search(
        r"```[a-zA-Z0-9+#-]*\s*\n(.*?)```",
        text,
        re.DOTALL,
    )

    if match:
        return match.group(1).strip()

    return text


def _clean_name(name: str) -> str:
    return name.strip().strip("`*\"' ").replace("\\", "/").lstrip("/")


def _build_prompt(project_name: str, errors: List[str], files: dict) -> str:
    error_text = "\n".join(f"- {error}" for error in errors)

    # Show the model the files most likely involved in the first error.
    mentioned = []

    for name in files:
        if any(name in error for error in errors):
            mentioned.append(name)

    if not mentioned:
        mentioned = list(files)[:3]

    file_text = ""

    for name in mentioned[:4]:
        content = files.get(name, "")

        if len(content) > config.MAX_FILE_CHARS:
            content = content[: config.MAX_FILE_CHARS] + "\n[truncated]"

        file_text += f"\n===FILE: {name}===\n{content}\n===END FILE===\n"

    inventory = "\n".join(f"- {name}" for name in files) or "- (none)"

    return f"""You are VOV AI's automatic repair agent.

PROJECT: {project_name}

ALL FILES IN THE PROJECT:
{inventory}

PROBLEMS DETECTED:
{error_text}

RELEVANT FILE CONTENTS:
{file_text}

Fix exactly ONE problem: the first one listed.

Rules:
1. Decide which single file must be created or changed.
2. Return that file's COMPLETE new contents, not a diff or a snippet.
3. Preserve everything that already works in that file.
4. Do not touch any other file.
5. No explanations, no markdown fences.

Respond in exactly this shape and nothing else:

FILE: path/name.ext
CONTENT:
<complete file contents>
"""


def fix_project(
    project_name: str,
    model: Optional[str] = None,
    max_attempts: Optional[int] = None,
) -> dict:
    if not project_exists(project_name):
        return {"working": False, "message": "Project does not exist.", "fixed_files": []}

    errors = test_project(project_name)

    if not errors:
        return {
            "working": True,
            "message": "Project is already healthy.",
            "fixed_files": [],
            "errors": [],
        }

    selected = resolve_model(model or config.FAST_MODEL)
    attempts = max_attempts or config.MAX_FIX_ATTEMPTS

    fixed_files: List[str] = []
    previous_errors: Optional[List[str]] = None

    for attempt in range(1, attempts + 1):
        errors = test_project(project_name)

        if not errors:
            return {
                "working": True,
                "message": f"Project repaired after {attempt - 1} change(s).",
                "fixed_files": fixed_files,
                "errors": [],
            }

        # No progress since the last round: stop burning cycles.
        if previous_errors is not None and errors == previous_errors:
            break

        previous_errors = errors

        update_status(
            project_name,
            "fixing",
            f"Repair attempt {attempt}: {errors[0]}",
        )

        files = read_project(project_name)

        try:
            response = ask_model(_build_prompt(project_name, errors, files), selected)
        except Exception as error:  # noqa: BLE001
            return {
                "working": False,
                "message": f"Repair failed: {error}",
                "fixed_files": fixed_files,
                "errors": errors,
            }

        name_match = FILE_PATTERN.search(response)
        body_match = CONTENT_PATTERN.search(response)

        if not name_match or not body_match:
            log(project_name, "Repair agent returned an unusable response.")
            break

        filename = _clean_name(name_match.group("name"))
        content = _strip_fences(body_match.group("body"))

        if not filename or not content:
            log(project_name, "Repair agent returned an empty file.")
            break

        try:
            original = read_file(project_name, filename)
        except ValueError as error:
            log(project_name, f"Repair agent returned an unsafe path: {filename}")

            return {
                "working": False,
                "message": str(error),
                "fixed_files": fixed_files,
                "errors": errors,
            }

        if original is not None and original.strip() == content.strip():
            log(project_name, f"Repair agent proposed no change to {filename}.")
            break

        try:
            create_file(project_name, filename, content)
        except ValueError as error:
            return {
                "working": False,
                "message": str(error),
                "fixed_files": fixed_files,
                "errors": errors,
            }

        if filename not in fixed_files:
            fixed_files.append(filename)

        log(project_name, f"Repaired {filename}")

    final_errors = test_project(project_name)

    if not final_errors:
        return {
            "working": True,
            "message": "Project repaired successfully.",
            "fixed_files": fixed_files,
            "errors": [],
        }

    return {
        "working": False,
        "message": "Some issues could not be repaired automatically.",
        "fixed_files": fixed_files,
        "errors": final_errors,
    }
