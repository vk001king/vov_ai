"""
VOV AI - Project validation.

The original only checked that index.html had a doctype. This version
also verifies referenced assets exist, balances braces in CSS and JS,
compiles Python files, parses JSON, and uses `node --check` when Node
is available for real JavaScript syntax checking.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from project_manager import project_path, read_project

_NODE = shutil.which("node")

# href/src values we should not try to resolve on disk.
_EXTERNAL = ("http://", "https://", "//", "data:", "mailto:", "tel:", "#", "javascript:")


def _local_refs(html: str) -> List[str]:
    refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)

    local = []

    for ref in refs:
        ref = ref.strip()

        if not ref or ref.lower().startswith(_EXTERNAL):
            continue

        local.append(ref.split("?")[0].split("#")[0])

    return local


def _balanced(text: str, opener: str, closer: str) -> bool:
    # Strip strings and comments so braces inside them do not count.
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    stripped = re.sub(r"(?m)//.*$", "", stripped)
    stripped = re.sub(r'"(?:\\.|[^"\\])*"', '""', stripped)
    stripped = re.sub(r"'(?:\\.|[^'\\])*'", "''", stripped)
    stripped = re.sub(r"`(?:\\.|[^`\\])*`", "``", stripped)

    return stripped.count(opener) == stripped.count(closer)


def _check_javascript(name: str, content: str, path: Path) -> List[str]:
    errors: List[str] = []

    if _NODE:
        try:
            result = subprocess.run(
                [_NODE, "--check", str(path)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                first = (result.stderr or "").strip().splitlines()
                detail = first[0] if first else "syntax error"
                errors.append(f"{name} has a JavaScript syntax error: {detail}")

            return errors

        except (subprocess.TimeoutExpired, OSError):
            pass  # Fall through to the heuristic check.

    if not _balanced(content, "{", "}"):
        errors.append(f"{name} has unbalanced curly braces.")

    if not _balanced(content, "(", ")"):
        errors.append(f"{name} has unbalanced parentheses.")

    return errors


def test_project(project_name: str) -> List[str]:
    """Return a list of human readable problems. Empty means healthy."""

    try:
        root = project_path(project_name)
    except ValueError as error:
        return [str(error)]

    if not root.is_dir():
        return ["Project directory does not exist."]

    files = read_project(project_name)

    if not files:
        return ["Project contains no readable files."]

    errors: List[str] = []

    all_names = {name.lower() for name in files}

    # --------------------------------------------------------------
    # Web projects
    # --------------------------------------------------------------

    html_files = [name for name in files if name.lower().endswith((".html", ".htm"))]

    is_python_only = not html_files and any(
        name.lower().endswith(".py") for name in files
    )

    if html_files:
        if "index.html" not in all_names:
            errors.append("No index.html found; the site has no entry point.")

        for name in html_files:
            html = files[name]
            lowered = html.lower()

            if "<!doctype html>" not in lowered:
                errors.append(f"{name} is missing a <!DOCTYPE html> declaration.")

            for tag in ("<html", "<head", "<body"):
                if tag not in lowered:
                    errors.append(f"{name} is missing the {tag}> element.")

            if "<title" not in lowered:
                errors.append(f"{name} has no <title> element.")

            # Referenced local assets must exist.
            for ref in _local_refs(html):
                target = (root / Path(name).parent / ref).resolve()

                try:
                    target.relative_to(root.resolve())
                except ValueError:
                    errors.append(f"{name} references a path outside the project: {ref}")
                    continue

                if not target.exists():
                    errors.append(f"{name} references {ref} but that file is missing.")

    elif not is_python_only:
        # Neither a website nor a Python program; only warn if truly empty.
        pass

    # --------------------------------------------------------------
    # Per-file syntax checks
    # --------------------------------------------------------------

    for name, content in files.items():
        suffix = Path(name).suffix.lower()

        if not content.strip():
            errors.append(f"{name} is empty.")
            continue

        if suffix == ".css":
            if not _balanced(content, "{", "}"):
                errors.append(f"{name} has unbalanced curly braces.")

        elif suffix in (".js", ".jsx", ".mjs"):
            errors.extend(_check_javascript(name, content, root / name))

        elif suffix == ".py":
            try:
                compile(content, name, "exec")
            except SyntaxError as error:
                errors.append(f"{name} has a Python syntax error on line {error.lineno}: {error.msg}")

        elif suffix == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                errors.append(f"{name} is not valid JSON: {error.msg} (line {error.lineno}).")

        # Leftover placeholders mean the model gave up halfway.
        for marker in ("TODO:", "YOUR CODE HERE", "ADD CODE HERE", "IMPLEMENT THIS"):
            if marker in content:
                errors.append(f"{name} contains an unfinished placeholder ({marker}).")
                break

    return errors


def project_report(project_name: str) -> dict:
    errors = test_project(project_name)
    files = read_project(project_name)

    return {
        "project": project_name,
        "working": len(errors) == 0,
        "errors": errors,
        "file_count": len(files),
        "node_available": bool(_NODE),
    }
