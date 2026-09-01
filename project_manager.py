from pathlib import Path


# ============================================================
# PROJECT STORAGE
# ============================================================

BASE_DIR = Path(__file__).parent / "generated_projects"


# ============================================================
# CREATE PROJECT
# ============================================================

def create_project(project_name):

    project_path = BASE_DIR / project_name

    project_path.mkdir(
        parents=True,
        exist_ok=True
    )

    return project_path


# ============================================================
# SAFE PATH CHECK
# ============================================================

def is_safe_path(file_path):

    path = Path(file_path)

    if path.is_absolute():
        return False

    if ".." in path.parts:
        return False

    return True


# ============================================================
# CREATE / UPDATE FILE
# ============================================================

def create_file(
    project_name,
    file_path,
    content
):

    project_path = BASE_DIR / project_name

    if not is_safe_path(file_path):

        raise ValueError(
            f"Unsafe file path: {file_path}"
        )

    full_path = project_path / file_path

    full_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    full_path.write_text(
        content,
        encoding="utf-8"
    )

    return full_path


# ============================================================
# READ PROJECT
# ============================================================

def read_project(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():

        return {}

    files = {}

    for file in project_path.rglob("*"):

        if not file.is_file():
            continue

        relative_path = file.relative_to(
            project_path
        )

        try:

            files[
                str(relative_path).replace(
                    "\\",
                    "/"
                )
            ] = file.read_text(
                encoding="utf-8"
            )

        except (
            UnicodeDecodeError,
            PermissionError
        ):

            continue

    return files


# ============================================================
# GET PROJECT CONTEXT
# ============================================================

def get_project_context(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():

        return ""

    context = []

    for file in project_path.rglob("*"):

        if not file.is_file():
            continue

        try:

            content = file.read_text(
                encoding="utf-8"
            )

            relative = file.relative_to(
                project_path
            )

            relative = str(
                relative
            ).replace(
                "\\",
                "/"
            )

            context.append(

                f"===FILE: {relative}===\n"
                f"{content}\n"
                f"===END FILE==="

            )

        except (
            UnicodeDecodeError,
            PermissionError
        ):

            continue

    return "\n\n".join(
        context
    )


# ============================================================
# CHECK PROJECT
# ============================================================

def project_exists(project_name):

    project_path = BASE_DIR / project_name

    return project_path.exists()


# ============================================================
# LIST PROJECT FILES
# ============================================================

def list_project_files(project_name):

    project_path = BASE_DIR / project_name

    if not project_path.exists():

        return []

    files = []

    for file in project_path.rglob("*"):

        if file.is_file():

            relative = file.relative_to(
                project_path
            )

            files.append(
                str(relative).replace(
                    "\\",
                    "/"
                )
            )

    return files


# ============================================================
# DELETE FILE
# ============================================================

def delete_file(
    project_name,
    file_path
):

    project_path = BASE_DIR / project_name

    if not is_safe_path(file_path):

        raise ValueError(
            f"Unsafe file path: {file_path}"
        )

    full_path = project_path / file_path

    if not full_path.exists():

        return False

    if not full_path.is_file():

        return False

    full_path.unlink()

    return True
