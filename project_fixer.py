from pathlib import Path
import re

from ollama_engine import ask_model
from project_tester import test_project


BASE_DIR = Path(__file__).parent / "generated_projects"


def extract_code(response):
    """
    Extract code from Qwen's response.
    Removes markdown fences and explanations.
    """

    response = response.strip()

    # Look for markdown code block
    match = re.search(
        r"```(?:html|css|javascript|js|text)?\s*(.*?)```",
        response,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return response


def fix_project(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():
        return {
            "working": False,
            "message": "Project does not exist."
        }

    # -----------------------------------------
    # TEST PROJECT
    # -----------------------------------------

    errors = test_project(project_name)

    if not errors:
        return {
            "working": True,
            "message": "Project is already working.",
            "fixed_files": []
        }

    fixed_files = []

    # -----------------------------------------
    # LIMIT AUTOMATIC FIXES
    # -----------------------------------------

    max_fixes = 5

    for attempt in range(max_fixes):

        errors = test_project(project_name)

        if not errors:
            return {
                "working": True,
                "message": "Project fixed successfully.",
                "fixed_files": fixed_files
            }

        error_text = "\n".join(
            f"- {error}"
            for error in errors
        )

        # -----------------------------------------
        # ASK QWEN
        # -----------------------------------------

        prompt = f"""
You are VOV AI's automatic software repair agent.

PROJECT:
{project_name}

PROJECT DIRECTORY:
{project_path}

CURRENT ERRORS:
{error_text}

Your task is to fix ONE error.

Rules:

1. Identify the file that needs to be created or modified.
2. Return the complete contents of that file.
3. Do NOT return explanations.
4. Do NOT return multiple files.
5. Do NOT use markdown code fences.
6. Do NOT modify unrelated files.

Return ONLY:

FILE: filename.ext

CONTENT:
<complete file content>
"""

        response = ask_model(prompt)

        # -----------------------------------------
        # FIND FILE NAME
        # -----------------------------------------

        file_match = re.search(
            r"FILE:\s*([^\s]+)",
            response,
            re.IGNORECASE
        )

        if not file_match:
            return {
                "working": False,
                "message": "AI could not identify the file to fix.",
                "ai_response": response,
                "fixed_files": fixed_files
            }

        filename = file_match.group(1).strip()

        if (
            ".." in filename
            or filename.startswith("/")
            or "\\" in filename
        ):
            return {
                "working": False,
                "message": "AI returned an unsafe file path.",
                "fixed_files": fixed_files
            }

        # -----------------------------------------
        # EXTRACT CONTENT
        # -----------------------------------------

        content_match = re.search(
            r"CONTENT:\s*(.*)",
            response,
            re.IGNORECASE | re.DOTALL
        )

        if not content_match:
            return {
                "working": False,
                "message": "AI did not return file content.",
                "ai_response": response,
                "fixed_files": fixed_files
            }

        content = extract_code(
            content_match.group(1)
        )

        if not content:
            return {
                "working": False,
                "message": "AI returned empty file content.",
                "fixed_files": fixed_files
            }

        # -----------------------------------------
        # WRITE FILE
        # -----------------------------------------

        target_file = project_path / filename

        target_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target_file.write_text(
            content,
            encoding="utf-8"
        )

        fixed_files.append(filename) 

    # -----------------------------------------
    # FINAL TEST
    # -----------------------------------------

    final_errors = test_project(
        project_name
    )

    if not final_errors:

        return {
            "working": True,
            "message": "Project fixed successfully.",
            "fixed_files": fixed_files
        }

    return {
        "working": False,
        "message": "AI attempted repairs but the project still has errors.",
        "errors": final_errors,
        "fixed_files": fixed_files
    }
