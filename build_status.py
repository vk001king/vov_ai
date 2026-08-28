from datetime import datetime


# Stores the current status of projects
builds = {}


def start_build(project_name):
    builds[project_name] = {
        "project": project_name,
        "status": "starting",
        "message": "Starting VOV AI...",
        "current_file": None,
        "completed_files": [],
        "errors": [],
        "started_at": datetime.now().isoformat(),
        "finished": False
    }


def update_status(
    project_name,
    status,
    message,
    current_file=None
):
    if project_name not in builds:
        start_build(project_name)

    builds[project_name]["status"] = status
    builds[project_name]["message"] = message
    builds[project_name]["current_file"] = current_file


def file_completed(project_name, filename):
    if project_name not in builds:
        start_build(project_name)

    if filename not in builds[project_name]["completed_files"]:
        builds[project_name]["completed_files"].append(filename)


def add_error(project_name, error):
    if project_name not in builds:
        start_build(project_name)

    builds[project_name]["errors"].append(error)


def finish_build(
    project_name,
    success=True,
    message="Project ready!"
):
    if project_name not in builds:
        start_build(project_name)

    builds[project_name]["status"] = (
        "complete" if success else "failed"
    )

    builds[project_name]["message"] = message
    builds[project_name]["current_file"] = None
    builds[project_name]["finished"] = True


def get_status(project_name):

    if project_name not in builds:
        return {
            "project": project_name,
            "status": "not_found",
            "message": "No active build found.",
            "current_file": None,
            "completed_files": [],
            "errors": [],
            "finished": True
        }

    return builds[project_name]