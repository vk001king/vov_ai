"""
VOV AI - Project file management.

Path safety is enforced by resolving the final path and confirming it
still sits inside the project directory. The original only did a string
check for "..", which symlinks and odd encodings can slip past.
"""

import io
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import config

BASE_DIR = config.PROJECTS_DIR

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


# ------------------------------------------------------------------
# Names and paths
# ------------------------------------------------------------------

def is_valid_project_name(project_name: str) -> bool:
    if not project_name or len(project_name) > 64:
        return False

    if project_name in (".", ".."):
        return False

    return bool(SAFE_NAME.match(project_name))


def project_path(project_name: str) -> Path:
    if not is_valid_project_name(project_name):
        raise ValueError(f"Invalid project name: {project_name!r}")

    return BASE_DIR / project_name


def safe_file_path(project_name: str, file_path: str) -> Path:
    """
    Resolve file_path inside the project and refuse anything that
    escapes it. Returns the absolute path.
    """

    root = project_path(project_name).resolve()

    cleaned = str(file_path).replace("\\", "/").strip()

    if not cleaned:
        raise ValueError("Empty file path.")

    # Reject absolute paths outright rather than silently reinterpreting
    # them as relative, which would hide the model's mistake.
    if cleaned.startswith("/") or re.match(r"^[A-Za-z]:", cleaned):
        raise ValueError(f"Absolute file paths are not allowed: {file_path}")

    if "\x00" in cleaned:
        raise ValueError("Invalid file path.")

    candidate = (root / cleaned).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Unsafe file path: {file_path}") from error

    return candidate


def _skip(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)

    if any(part in config.IGNORED_DIRS for part in relative.parts):
        return True

    return path.suffix.lower() in config.BINARY_SUFFIXES


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

def create_project(project_name: str) -> Path:
    path = project_path(project_name)
    path.mkdir(parents=True, exist_ok=True)

    return path


def project_exists(project_name: str) -> bool:
    try:
        return project_path(project_name).is_dir()
    except ValueError:
        return False


def create_file(project_name: str, file_path: str, content: str) -> Path:
    full_path = safe_file_path(project_name, file_path)

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")

    return full_path


def delete_file(project_name: str, file_path: str) -> bool:
    full_path = safe_file_path(project_name, file_path)

    if not full_path.is_file():
        return False

    full_path.unlink()

    return True


def delete_project(project_name: str) -> bool:
    path = project_path(project_name)

    if not path.is_dir():
        return False

    shutil.rmtree(path)

    return True


def rename_project(project_name: str, new_name: str) -> bool:
    source = project_path(project_name)
    target = project_path(new_name)

    if not source.is_dir() or target.exists():
        return False

    source.rename(target)

    return True


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

def read_file(project_name: str, file_path: str) -> Optional[str]:
    full_path = safe_file_path(project_name, file_path)

    if not full_path.is_file():
        return None

    try:
        return full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def read_project(project_name: str) -> Dict[str, str]:
    """Every readable text file in the project, keyed by relative path."""

    root = project_path(project_name)

    if not root.is_dir():
        return {}

    files: Dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file() or _skip(path, root):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError, OSError):
            continue

        relative = str(path.relative_to(root)).replace("\\", "/")
        files[relative] = content

    return files


def list_project_files(project_name: str) -> List[dict]:
    root = project_path(project_name)

    if not root.is_dir():
        return []

    entries: List[dict] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(part in config.IGNORED_DIRS for part in relative.parts):
            continue

        entries.append(
            {
                "name": str(relative).replace("\\", "/"),
                "size": path.stat().st_size,
                "binary": path.suffix.lower() in config.BINARY_SUFFIXES,
            }
        )

    return entries


def list_projects() -> List[dict]:
    if not BASE_DIR.is_dir():
        return []

    projects: List[dict] = []

    for path in sorted(BASE_DIR.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue

        files = [item for item in path.rglob("*") if item.is_file()]

        total = sum(item.stat().st_size for item in files) if files else 0
        newest = max((item.stat().st_mtime for item in files), default=path.stat().st_mtime)

        projects.append(
            {
                "name": path.name,
                "files": len(files),
                "size": total,
                "updated_at": newest,
                "has_index": (path / "index.html").is_file(),
            }
        )

    projects.sort(key=lambda item: item["updated_at"], reverse=True)

    return projects


# ------------------------------------------------------------------
# Model context
# ------------------------------------------------------------------

def get_project_context(project_name: str) -> str:
    """
    Project files formatted for the model, capped so a big project
    cannot blow past the context window.
    """

    files = read_project(project_name)

    if not files:
        return ""

    # Prioritise entry points, then smaller files.
    priority = ["index.html", "style.css", "script.js", "main.py", "app.py", "README.md"]

    def rank(item):
        name = item[0]
        return (0, priority.index(name)) if name in priority else (1, len(item[1]))

    ordered = sorted(files.items(), key=rank)

    blocks: List[str] = []
    total = 0

    for index, (name, content) in enumerate(ordered):
        if index >= config.MAX_CONTEXT_FILES:
            blocks.append(f"[{len(ordered) - index} more files omitted for length]")
            break

        if len(content) > config.MAX_FILE_CHARS:
            content = content[: config.MAX_FILE_CHARS] + "\n[file truncated]"

        block = f"===FILE: {name}===\n{content}\n===END FILE==="

        if total + len(block) > config.MAX_TOTAL_CONTEXT_CHARS:
            blocks.append("[remaining files omitted for length]")
            break

        blocks.append(block)
        total += len(block)

    return "\n\n".join(blocks)


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------

def zip_project(project_name: str) -> Optional[io.BytesIO]:
    root = project_path(project_name)

    if not root.is_dir():
        return None

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(root)

            if any(part in config.IGNORED_DIRS for part in relative.parts):
                continue

            archive.write(path, arcname=str(Path(project_name) / relative))

    buffer.seek(0)

    return buffer
