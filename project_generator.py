import re
from pathlib import Path

from ollama_engine import ask_model
from project_manager import create_project, create_file

from build_status import (
    start_build,
    update_status,
    file_completed,
    finish_build,
    add_error
)


BASE_DIR = Path(__file__).parent / "generated_projects"


def extract_files(response):
    """
    Extract files from the AI response using:

    ===FILE: filename===
    content
    ===END FILE===
    """

    pattern = r"===FILE:\s*(.*?)===\s*\n(.*?)\n===END FILE==="

    matches = re.findall(
        pattern,
        response,
        re.DOTALL | re.IGNORECASE
    )

    files = []

    for filename, content in matches:

        filename = filename.strip()
        content = content.strip()

        if filename and content:

            files.append({
                "name": filename,
                "content": content
            })

    return files


def generate_project(project_name, user_request):

    # ==========================================
    # START BUILD
    # ==========================================

    start_build(project_name)

    update_status(
        project_name,
        "thinking",
        "Understanding your request..."
    )

    try:

        # ======================================
        # PLANNING
        # ======================================

        update_status(
            project_name,
            "planning",
            "Planning the project structure..."
        )

        prompt = f"""
You are VOV AI, an AI software and website builder.

USER REQUEST:

{user_request}

Create a complete, functional project.

You MUST generate every file required for the project to work.

For example, for a normal website you should normally create:

index.html
style.css
script.js

If the project requires additional files, create them too.

IMPORTANT:

- Do not leave required files missing.
- Make the website functional.
- Make the UI modern and attractive.
- Make JavaScript functional where required.
- Make sure all referenced files actually exist.
- Do not explain anything.
- Do not use JSON.
- Do not use Markdown code fences.

Use EXACTLY this format:

===FILE: index.html===
complete HTML code
===END FILE===

===FILE: style.css===
complete CSS code
===END FILE===

===FILE: script.js===
complete JavaScript code
===END FILE===

For additional files use the same format.

Return ONLY the files.
"""

        # ======================================
        # GENERATING
        # ======================================

        update_status(
            project_name,
            "generating",
            "Qwen3.5 is generating your project..."
        )

        response = ask_model(prompt)

        # ======================================
        # EXTRACT FILES
        # ======================================

        files = extract_files(response)

        if not files:

            raise ValueError(
                "Qwen3.5 did not return files in the expected format."
            )

        # ======================================
        # CREATE PROJECT
        # ======================================

        update_status(
            project_name,
            "creating",
            "Creating project directory..."
        )

        create_project(project_name)

        # ======================================
        # CREATE FILES
        # ======================================

        created_files = []

        for file_data in files:

            filename = file_data["name"]
            content = file_data["content"]

            # Security protection
            filename = filename.replace("\\", "/")

            if (
                filename.startswith("/")
                or ".." in Path(filename).parts
            ):
                continue

            update_status(
                project_name,
                "generating_file",
                f"Working on {filename}...",
                filename
            )

            create_file(
                project_name,
                filename,
                content
            )

            file_completed(
                project_name,
                filename
            )

            created_files.append(filename)

        # ======================================
        # TESTING
        # ======================================

        update_status(
            project_name,
            "testing",
            "Testing the generated project..."
        )

        # ======================================
        # FINISH
        # ======================================

        finish_build(
            project_name,
            success=True,
            message="Project generated successfully!"
        )

        return {
            "project": project_name,
            "files": created_files
        }

    except Exception as e:

        error_message = str(e)

        add_error(
            project_name,
            error_message
        )

        finish_build(
            project_name,
            success=False,
            message="Project generation failed."
        )

        return {
            "project": project_name,
            "files": [],
            "error": error_message
        }