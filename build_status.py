"""
VOV AI - Build status tracking.

The original stored state in a bare dict mutated from background
threads. This version is lock protected, keeps a rolling log, and
supports cancellation so a runaway build can be stopped.
"""

import threading
from datetime import datetime
from typing import Dict, List, Optional

_lock = threading.RLock()

_builds: Dict[str, dict] = {}

MAX_LOG_LINES = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _blank(project_name: str) -> dict:
    return {
        "project": project_name,
        "status": "starting",
        "message": "Starting VOV AI...",
        "current_file": None,
        "completed_files": [],
        "errors": [],
        "log": [],
        "model": None,
        "mode": None,
        "progress": 0,
        "started_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
        "finished": False,
        "cancel_requested": False,
    }


def start_build(project_name: str, model: Optional[str] = None, mode: Optional[str] = None) -> dict:
    with _lock:
        build = _blank(project_name)
        build["model"] = model
        build["mode"] = mode
        _builds[project_name] = build

        return dict(build)


def is_running(project_name: str) -> bool:
    with _lock:
        build = _builds.get(project_name)
        return bool(build) and not build["finished"]


def log(project_name: str, line: str) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))

        build["log"].append({"at": _now(), "line": line})

        if len(build["log"]) > MAX_LOG_LINES:
            build["log"] = build["log"][-MAX_LOG_LINES:]

        build["updated_at"] = _now()


def update_status(
    project_name: str,
    status: str,
    message: str,
    current_file: Optional[str] = None,
    progress: Optional[int] = None,
) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))

        build["status"] = status
        build["message"] = message
        build["current_file"] = current_file
        build["updated_at"] = _now()

        if progress is not None:
            build["progress"] = max(0, min(100, int(progress)))

    log(project_name, message)


def set_model(project_name: str, model: str) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))
        build["model"] = model


def file_completed(project_name: str, filename: str) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))

        if filename not in build["completed_files"]:
            build["completed_files"].append(filename)

        build["updated_at"] = _now()

    log(project_name, f"Wrote {filename}")


def add_error(project_name: str, error: str) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))
        build["errors"].append(str(error))
        build["updated_at"] = _now()

    log(project_name, f"Error: {error}")


def request_cancel(project_name: str) -> bool:
    with _lock:
        build = _builds.get(project_name)

        if not build or build["finished"]:
            return False

        build["cancel_requested"] = True
        build["message"] = "Cancelling..."
        build["updated_at"] = _now()

        return True


def cancel_requested(project_name: str) -> bool:
    with _lock:
        build = _builds.get(project_name)
        return bool(build and build["cancel_requested"])


def finish_build(
    project_name: str,
    success: bool = True,
    message: str = "Project ready.",
) -> None:
    with _lock:
        build = _builds.setdefault(project_name, _blank(project_name))

        build["status"] = "complete" if success else "failed"
        build["message"] = message
        build["current_file"] = None
        build["finished"] = True
        build["finished_at"] = _now()
        build["updated_at"] = _now()
        build["progress"] = 100 if success else build["progress"]

    log(project_name, message)


def get_status(project_name: str) -> dict:
    with _lock:
        build = _builds.get(project_name)

        if not build:
            return {
                "project": project_name,
                "status": "not_found",
                "message": "No active build found.",
                "current_file": None,
                "completed_files": [],
                "errors": [],
                "log": [],
                "model": None,
                "mode": None,
                "progress": 0,
                "started_at": None,
                "updated_at": None,
                "finished_at": None,
                "finished": True,
                "cancel_requested": False,
            }

        import copy

        return copy.deepcopy(build)


def list_builds() -> List[dict]:
    with _lock:
        return [
            {
                "project": build["project"],
                "status": build["status"],
                "message": build["message"],
                "finished": build["finished"],
                "updated_at": build["updated_at"],
            }
            for build in _builds.values()
        ]


def clear_finished() -> int:
    with _lock:
        done = [name for name, build in _builds.items() if build["finished"]]

        for name in done:
            _builds.pop(name, None)

        return len(done)
