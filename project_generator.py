import re
from pathlib import Path

from ollama_engine import ask_model, select_model

from project_manager import (
    create_project,
    create_file,
    read_project,
    project_exists
)

from build_status import (
    start_build,
    update_status,
    file_completed,
    finish_build,
    add_error
)


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).parent / "generated_projects"


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_files(response):
    """
    Extract files from the AI response.

    Expected format:

    ===FILE: index.html===
    code
    ===END FILE===
    """

    pattern = r"===FILE:\s*(.*?)===\s*\n(.*?)\s*===END FILE==="

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


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(request):

    text = request.lower()

    languages = {

        "python": [
            "only python",
            "use only python",
            "use python",
            "python",
            "python program",
            "python app",
            "python application"
        ],

        "javascript": [
            "only javascript",
            "use only javascript",
            "use javascript",
            "javascript",
            "javascript app",
            "js"
        ],

        "typescript": [
            "only typescript",
            "use typescript",
            "typescript",
            "typescript app",
            "ts"
        ],

        "react": [
            "only react",
            "use react",
            "react",
            "reactjs",
            "react.js"
        ],

        "html": [
            "only html",
            "use html",
            "html",
            "html css",
            "html website"
        ],

        "java": [
            "only java",
            "use java",
            "java"
        ],

        "c++": [
            "only c++",
            "use c++",
            "c++"
        ],

        "c": [
            "only c programming",
            "use c programming",
            "c programming"
        ],

        "php": [
            "only php",
            "use php",
            "php"
        ],

        "node": [
            "only node",
            "use node",
            "node",
            "nodejs",
            "node.js"
        ]
    }

    for language, keywords in languages.items():

        for keyword in keywords:

            if keyword in text:

                return language

    return "auto"


# ============================================================
# PROJECT TYPE
# ============================================================

def detect_project_type(request):

    text = request.lower()

    if "react" in text:
        return "React application"

    if "website" in text:
        return "website"

    if "web app" in text:
        return "web application"

    if "python" in text:
        return "Python application"

    if "application" in text or " app" in text:
        return "application"

    return "software project"


# ============================================================
# MODIFICATION DETECTION
# ============================================================

def is_modification_request(request):

    text = request.lower()

    modification_words = [

        "change",
        "modify",
        "update",
        "edit",
        "add",
        "remove",
        "delete",
        "replace",
        "improve",
        "fix",
        "redesign",
        "adjust",
        "rename",
        "include",
        "make it",
        "make the",
        "add a",
        "add an"
    ]

    for word in modification_words:

        if word in text:

            return True

    return False


# ============================================================
# EXISTING PROJECT
# ============================================================

def get_existing_files(project_name):

    if not project_exists(project_name):

        return {}

    return read_project(
        project_name
    )


# ============================================================
# GENERATION PROMPT
# ============================================================

def build_generation_prompt(
    user_request,
    selected_model,
    existing_files=None
):

    language = detect_language(
        user_request
    )

    project_type = detect_project_type(
        user_request
    )

    existing_files = existing_files or {}


    # ========================================================
    # LANGUAGE
    # ========================================================

    if language != "auto":

        language_instruction = f"""
The user explicitly requested:

{language}

You MUST use this technology.

Do NOT replace it with another programming language
or framework.
"""

    else:

        language_instruction = """
The user did not specify a programming language.

Choose the best technology automatically.

Consider:

- requirements
- performance
- simplicity
- maintainability
- browser compatibility
- functionality
- scalability
"""


    # ========================================================
    # EXISTING PROJECT
    # ========================================================

    if existing_files:

        existing_section = """
============================================================
EXISTING PROJECT
============================================================

This project already exists.

The user wants to modify the existing project.

Read and understand the existing files carefully.

IMPORTANT:

- Preserve existing functionality.
- Do not unnecessarily rewrite unrelated files.
- Do not remove existing features.
- Do not break existing APIs.
- Do not break existing links.
- Do not break existing JavaScript.
- Do not break existing CSS.
- Only change what is required.
- Add new files only when necessary.
- Return complete contents of every file you modify.

Existing files:

"""

        for filename, content in existing_files.items():

            existing_section += f"""

============================================================
FILE: {filename}
============================================================

{content}

============================================================
END FILE
============================================================

"""

    else:

        existing_section = """
============================================================
NEW PROJECT
============================================================

This is a new project.

Create the complete project from scratch.
"""


    # ========================================================
    # PROMPT
    # ========================================================

    return f"""
You are VOV AI, an advanced autonomous software development
agent.

You create and modify complete working software projects.

============================================================
SELECTED MODEL
============================================================

{selected_model}

============================================================
PROJECT TYPE
============================================================

{project_type}

============================================================
USER REQUEST
============================================================

{user_request}

============================================================
LANGUAGE
============================================================

{language_instruction}

{existing_section}

============================================================
FUNCTIONALITY
============================================================

Create a complete and functional implementation.

Every requested feature must actually work.

Do not create fake buttons.

Do not create fake forms.

Do not create fake functionality.

Do not use placeholders.

Do not use:

TODO

YOUR CODE HERE

ADD CODE HERE

PLACEHOLDER

...

============================================================
MODIFICATION RULES
============================================================

If this is an existing project:

1. Understand the existing project.

2. Find the files related to the request.

3. Modify only what is necessary.

4. Preserve existing functionality.

5. Preserve existing design unless asked to change it.

6. Preserve existing APIs.

7. Preserve existing features.

8. Add new files when necessary.

9. Remove files only when explicitly requested.

10. Make sure all references are valid.

11. Make sure every imported file exists.

12. Make sure every HTML, CSS and JavaScript reference works.

13. Return COMPLETE files, not partial snippets.

============================================================
WEBSITE RULES
============================================================

For normal websites use:

HTML
CSS
JavaScript

unless another technology is explicitly requested.

The interface should be:

- modern
- attractive
- responsive
- accessible
- interactive
- functional

============================================================
CODE QUALITY
============================================================

Write clean and maintainable code.

Use meaningful variable names.

Avoid unnecessary duplication.

Handle errors properly.

Make sure the project can actually run.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY project files.

Use exactly:

===FILE: filename===

complete file contents

===END FILE===

Example:

===FILE: index.html===
<!DOCTYPE html>

<html>
...
</html>
===END FILE===

===FILE: style.css===
body {{
    margin: 0;
}}
===END FILE===

===FILE: script.js===
console.log("VOV AI");
===END FILE===

============================================================
OUTPUT RULES
============================================================

Do NOT return explanations.

Do NOT return Markdown code fences.

Do NOT return JSON.

Do NOT return commentary.

Do NOT return partial files.

Return complete files.

Before returning, verify:

- syntax
- imports
- references
- requested features
- existing features
- dependencies
- HTML
- CSS
- JavaScript

Then return ONLY the files.
"""


# ============================================================
# GENERATE / MODIFY PROJECT
# ============================================================

def generate_project(
    project_name,
    user_request,
    requested_model="auto",
    mode="auto"
):

    start_build(
        project_name
    )

    update_status(
        project_name,
        "thinking",
        "Understanding your request..."
    )

    try:

        # ====================================================
        # EXISTING PROJECT
        # ====================================================

        existing_files = get_existing_files(
            project_name
        )


        # ====================================================
        # NORMALIZE MODE
        # ====================================================

        mode = (
            mode or "auto"
        ).lower().strip()


        if mode not in [
            "auto",
            "create",
            "modify"
        ]:

            mode = "auto"


        # ====================================================
        # DECIDE CREATE / MODIFY
        # ====================================================

        if mode == "create":

            modifying = False

        elif mode == "modify":

            modifying = bool(
                existing_files
            )

        else:

            modifying = (
                bool(existing_files)
                and
                is_modification_request(
                    user_request
                )
            )


        # ====================================================
        # MODEL
        # ====================================================

        update_status(
            project_name,
            "planning",
            "Selecting the best AI model..."
        )

        selected_model = select_model(
            user_request,
            requested_model
        )


        update_status(
            project_name,
            "planning",
            f"Using {selected_model}..."
        )


        # ====================================================
        # MODE STATUS
        # ====================================================

        if modifying:

            update_status(
                project_name,
                "reading",
                "Reading existing project..."
            )

            update_status(
                project_name,
                "planning",
                "Planning requested changes..."
            )

        else:

            update_status(
                project_name,
                "planning",
                "Planning new project..."
            )


        # ====================================================
        # BUILD PROMPT
        # ====================================================

        prompt = build_generation_prompt(

            user_request,

            selected_model,

            existing_files if modifying else None

        )


        # ====================================================
        # AI GENERATION
        # ====================================================

        update_status(
            project_name,
            "generating",
            f"{selected_model} is working..."
        )


        response = ask_model(
            prompt,
            selected_model
        )


        # ====================================================
        # EXTRACT FILES
        # ====================================================

        update_status(
            project_name,
            "processing",
            "Processing generated files..."
        )


        files = extract_files(
            response
        )


        if not files:

            raise ValueError(
                "The AI did not return files in the expected format."
            )


        # ====================================================
        # CREATE PROJECT
        # ====================================================

        create_project(
            project_name
        )


        # ====================================================
        # SAVE FILES
        # ====================================================

        created_files = []

        for file_data in files:

            filename = file_data["name"]

            content = file_data["content"]


            # ------------------------------------------------
            # NORMALIZE PATH
            # ------------------------------------------------

            filename = filename.replace(
                "\\",
                "/"
            )

            path = Path(
                filename
            )


            # ------------------------------------------------
            # SECURITY
            # ------------------------------------------------

            if (
                filename.startswith("/")
                or
                filename.startswith("\\")
                or
                ".." in path.parts
            ):

                add_error(
                    project_name,
                    f"Unsafe file path skipped: {filename}"
                )

                continue


            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            update_status(

                project_name,

                "generating_file",

                f"Working on {filename}...",

                filename

            )


            # ------------------------------------------------
            # WRITE
            # ------------------------------------------------

            create_file(

                project_name,

                filename,

                content

            )


            # ------------------------------------------------
            # COMPLETE
            # ------------------------------------------------

            file_completed(

                project_name,

                filename

            )


            created_files.append(
                filename
            )


        # ====================================================
        # VALIDATION
        # ====================================================

        if not created_files:

            raise ValueError(
                "No valid project files were created."
            )


        # ====================================================
        # TEST
        # ====================================================

        update_status(
            project_name,
            "testing",
            "Checking generated project..."
        )


        # ====================================================
        # SUCCESS
        # ====================================================

        if modifying:

            success_message = (
                "Project modified successfully!"
            )

        else:

            success_message = (
                "Project generated successfully!"
            )


        finish_build(

            project_name,

            success=True,

            message=success_message

        )


        return {

            "project": project_name,

            "files": created_files,

            "model": selected_model,

            "language": detect_language(
                user_request
            ),

            "modified": modifying,

            "mode": (
                "modify"
                if modifying
                else "create"
            ),

            "success": True

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

            "model": requested_model,

            "success": False,

            "error": error_message

        }
